package com.harshit.harshcraft.ai;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import net.minecraft.client.Minecraft;
import net.minecraft.client.player.Input;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.network.chat.Component;
import net.minecraft.tags.FluidTags;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.item.ItemEntity;
import net.minecraft.world.entity.monster.Enemy;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.inventory.AbstractContainerMenu;
import net.minecraft.world.inventory.AbstractFurnaceMenu;
import net.minecraft.world.inventory.ClickType;
import net.minecraft.world.inventory.CraftingMenu;
import net.minecraft.world.inventory.Slot;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.HitResult;
import net.minecraft.world.phys.Vec3;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;

/**
 * HarshCraft AI environment (client side).
 *
 * Every method except the constructor MUST be called on the Minecraft client
 * thread. {@link AIHttpServer} guarantees that via Minecraft#execute.
 *
 * Protocol: Python submits ONE action ("step"). The action is executed for
 * "ticks" client ticks (or until it finishes early, e.g. a block was broken)
 * and the resulting observation is returned. This makes stepping synchronous
 * and deterministic: no goal can be overshot between observation and action.
 *
 * Input injection (movement + look) happens in {@link #applyInput()}, called
 * once per tick from KeyboardInputMixin. Everything else (digging, attacking,
 * placing, container clicks) happens in {@link #tick()}, called once per tick
 * from END_CLIENT_TICK. The two never overlap, so nothing runs twice.
 */
public class AIEnvironment {

    /** Local voxel window: x,z in [-R,R], y in [YMIN,YMAX] relative to the player's block. */
    public static final int R = 10;
    public static final int YMIN = -4;
    public static final int YMAX = 5;
    private static final double ENTITY_RADIUS = 24.0D;
    private static final double DIG_REACH = 4.8D;
    private static final double ATTACK_REACH_SQ = 2.95D * 2.95D;

    private final Minecraft mc;

    /* ---------------- active step ---------------- */
    private JsonObject act;
    private CompletableFuture<JsonObject> pending;
    private int ticksLeft;
    private int actionAge;
    private String result = "ok";

    /* ---------------- dig state ---------------- */
    private BlockPos digPos;
    private boolean digStarted;

    private boolean useHeld;
    private boolean aiSprint;

    public AIEnvironment(Minecraft minecraft) {
        this.mc = minecraft;
    }

    /* ======================================================================
     * SUBMIT / FINISH
     * ====================================================================== */

    public CompletableFuture<JsonObject> submit(JsonObject action) {
        finish("preempted");
        CompletableFuture<JsonObject> future = new CompletableFuture<>();
        if (mc.player == null || mc.level == null) {
            future.complete(error("no_player"));
            return future;
        }
        act = action;
        pending = future;
        ticksLeft = Math.max(1, Math.min(2400, num(action, "ticks", 1)));
        actionAge = 0;
        result = "ok";
        String op = str(action, "do", "none");
        if (!op.equals("dig")) {
            abortDig();
        }
        if (!op.equals("eat")) {
            releaseUse();
        }
        return future;
    }

    /** Cancel whatever is pending (pause, world exit, shutdown). */
    public void stopAction() {
        if (pending != null) {
            String why = (mc.player == null || mc.level == null) ? "no_player" : "paused";
            finish(why);
        }
        abortDig();
        releaseUse();
    }

    private void finish(String res) {
        if (pending == null) {
            act = null;
            return;
        }
        CompletableFuture<JsonObject> f = pending;
        pending = null;
        JsonObject obs = observe();
        obs.addProperty("result", res);
        obs.addProperty("ticks_run", actionAge);
        act = null;
        releaseUse();
        f.complete(obs);
    }

    /* ======================================================================
     * INPUT PHASE  (KeyboardInput.tick RETURN)
     * ====================================================================== */

    public void applyInput() {
        if (act == null || mc.player == null || mc.level == null || mc.isPaused()) {
            return;
        }
        Player p = mc.player;
        Input in = mc.player.input;

        /* ---- look ---- */
        float maxTurn = (float) num(act, "max_turn", 180.0D);
        Vec3 target = lookTarget();
        float wantYaw = p.getYRot();
        float wantPitch = p.getXRot();
        boolean setYaw = false;
        boolean setPitch = false;
        if (target != null) {
            Vec3 eye = p.getEyePosition();
            double dx = target.x - eye.x;
            double dy = target.y - eye.y;
            double dz = target.z - eye.z;
            double horiz = Math.sqrt(dx * dx + dz * dz);
            if (horiz > 1.0E-4D) {
                wantYaw = (float) (Math.toDegrees(Math.atan2(dz, dx)) - 90.0D);
                setYaw = true;
            }
            wantPitch = (float) -Math.toDegrees(Math.atan2(dy, Math.max(horiz, 1.0E-4D)));
            setPitch = true;
        } else {
            if (act.has("yaw")) {
                wantYaw = (float) num(act, "yaw", wantYaw);
                setYaw = true;
            } else if (act.has("dyaw")) {
                wantYaw = p.getYRot() + (float) num(act, "dyaw", 0.0D);
                setYaw = true;
            }
            if (act.has("pitch")) {
                wantPitch = (float) num(act, "pitch", wantPitch);
                setPitch = true;
            } else if (act.has("dpitch")) {
                wantPitch = p.getXRot() + (float) num(act, "dpitch", 0.0D);
                setPitch = true;
            }
        }
        if (setYaw) {
            float delta = wrap(wantYaw - p.getYRot());
            delta = Math.max(-maxTurn, Math.min(maxTurn, delta));
            p.setYRot(p.getYRot() + delta);
        }
        if (setPitch) {
            wantPitch = Math.max(-90.0F, Math.min(90.0F, wantPitch));
            float delta = wantPitch - p.getXRot();
            delta = Math.max(-maxTurn, Math.min(maxTurn, delta));
            p.setXRot(p.getXRot() + delta);
        }

        /* ---- movement (fully overrides the keyboard while a step is active) ---- */
        int fwd = Integer.signum(num(act, "fwd", 0));
        int strafe = Integer.signum(num(act, "strafe", 0));
        boolean jump = bool(act, "jump");
        boolean sneak = bool(act, "sneak");
        boolean sprint = bool(act, "sprint");

        in.forwardImpulse = fwd;
        in.leftImpulse = strafe;
        in.up = fwd > 0;
        in.down = fwd < 0;
        in.left = strafe > 0;
        in.right = strafe < 0;
        in.jumping = jump;
        in.shiftKeyDown = sneak;
        if (sneak) {
            in.forwardImpulse *= 0.3F;
            in.leftImpulse *= 0.3F;
        }
        if (fwd > 0 && sprint && !sneak && p.getFoodData().getFoodLevel() > 6) {
            p.setSprinting(true);
            aiSprint = true;
        } else if (aiSprint) {
            p.setSprinting(false);
            aiSprint = false;
        }
    }

    private Vec3 lookTarget() {
        if (act.has("look_at")) {
            JsonArray a = act.getAsJsonArray("look_at");
            return new Vec3(a.get(0).getAsDouble(), a.get(1).getAsDouble(), a.get(2).getAsDouble());
        }
        String op = str(act, "do", "none");
        if (op.equals("attack")) {
            Entity e = mc.level.getEntity(num(act, "entity", -1));
            if (e != null) {
                return e.position().add(0.0D, e.getBbHeight() * 0.6D, 0.0D);
            }
        } else if (op.equals("dig") || op.equals("use") || op.equals("place")) {
            BlockPos pos = readPos(act, "pos");
            if (pos != null) {
                Vec3 c = Vec3.atCenterOf(pos);
                if (op.equals("place")) {
                    Direction f = readFace(act);
                    c = c.add(f.getStepX() * 0.5D, f.getStepY() * 0.5D, f.getStepZ() * 0.5D);
                }
                return c;
            }
        }
        return null;
    }

    /* ======================================================================
     * TICK PHASE  (END_CLIENT_TICK)
     * ====================================================================== */

    public void tick() {
        if (pending == null) {
            return;
        }
        if (mc.player == null || mc.level == null) {
            finish("no_player");
            return;
        }
        if (mc.isPaused()) {
            return;
        }
        String op = str(act, "do", "none");
        boolean done = false;
        try {
            if (actionAge == 0) {
                oneShot(op);
            }
            done = runOp(op);
        } catch (Throwable t) {
            result = "exception:" + t.getClass().getSimpleName();
            done = true;
        }
        actionAge++;
        ticksLeft--;
        if (done || ticksLeft <= 0) {
            finish(result);
        }
    }

    /** Things that happen exactly once, on the first tick of a step. */
    private void oneShot(String op) {
        Player p = mc.player;
        if (act.has("hotbar")) {
            int slot = num(act, "hotbar", p.getInventory().selected);
            if (slot >= 0 && slot <= 8) {
                p.getInventory().selected = slot;
            }
        }
        switch (op) {
            case "command": {
                String cmd = str(act, "cmd", "");
                if (cmd.startsWith("/")) {
                    cmd = cmd.substring(1);
                }
                if (!cmd.isEmpty() && mc.player.connection != null) {
                    mc.player.connection.sendCommand(cmd);
                }
                break;
            }
            case "say":
                p.displayClientMessage(Component.literal(str(act, "msg", "")), false);
                break;
            case "click": {
                AbstractContainerMenu m = p.containerMenu;
                int slot = num(act, "slot", -1);
                if (m != null && slot >= 0 && slot < m.slots.size() && mc.gameMode != null) {
                    ClickType type = ClickType.PICKUP;
                    String mode = str(act, "mode", "pickup");
                    if (mode.equals("quick_move")) {
                        type = ClickType.QUICK_MOVE;
                    } else if (mode.equals("swap")) {
                        type = ClickType.SWAP;
                    } else if (mode.equals("throw")) {
                        type = ClickType.THROW;
                    }
                    mc.gameMode.handleInventoryMouseClick(m.containerId, slot, num(act, "button", 0), type, p);
                } else {
                    result = "bad_slot";
                }
                break;
            }
            case "close":
                mc.player.closeContainer();
                break;
            case "respawn":
                if (p.isDeadOrDying()) {
                    mc.player.respawn();
                }
                break;
            default:
                break;
        }
    }

    /** One tick of the active operation. Returns true when the operation is finished. */
    private boolean runOp(String op) {
        switch (op) {
            case "dig":
                return runDig();
            case "attack":
                return runAttack();
            case "use":
                return runUse();
            case "place":
                return runPlace();
            case "eat":
                mc.options.keyUse.setDown(true);
                useHeld = true;
                return false;
            case "click":
            case "close":
            case "command":
            case "say":
            case "respawn":
                return actionAge >= 1;
            default:
                return false;
        }
    }

    private boolean runDig() {
        BlockPos pos = readPos(act, "pos");
        if (pos == null || mc.gameMode == null) {
            result = "bad_args";
            return true;
        }
        Player p = mc.player;
        BlockState state = mc.level.getBlockState(pos);
        if (state.isAir()) {
            result = digStarted && pos.equals(digPos) ? "broken" : "already_air";
            digStarted = false;
            digPos = null;
            return true;
        }
        if (p.getEyePosition().distanceTo(Vec3.atCenterOf(pos)) > DIG_REACH) {
            result = "too_far";
            return true;
        }
        Vec3 eye = p.getEyePosition();
        Vec3 c = Vec3.atCenterOf(pos);
        Direction face = Direction.getNearest(eye.x - c.x, eye.y - c.y, eye.z - c.z);
        if (!digStarted || !pos.equals(digPos)) {
            abortDig();
            digStarted = mc.gameMode.startDestroyBlock(pos, face);
            digPos = digStarted ? pos : null;
            if (!digStarted) {
                result = "cannot_start";
                return true;
            }
        } else {
            mc.gameMode.continueDestroyBlock(pos, face);
        }
        p.swing(InteractionHand.MAIN_HAND);
        result = "digging";
        return false;
    }

    private boolean runAttack() {
        Player p = mc.player;
        Entity e = mc.level.getEntity(num(act, "entity", -1));
        if (e == null || !e.isAlive() || mc.gameMode == null) {
            result = "gone";
            return true;
        }
        if (e.getBoundingBox().distanceToSqr(p.getEyePosition()) > ATTACK_REACH_SQ) {
            result = "out_of_reach";
            return true;
        }
        if (p.getAttackStrengthScale(0.5F) < 0.95F) {
            result = "cooldown";
            return false;
        }
        mc.gameMode.attack(p, e);
        p.swing(InteractionHand.MAIN_HAND);
        result = "hit";
        return true;
    }

    private boolean runUse() {
        BlockPos pos = readPos(act, "pos");
        if (pos == null || mc.gameMode == null) {
            result = "bad_args";
            return true;
        }
        Player p = mc.player;
        Direction face = readFace(act);
        BlockHitResult hit = new BlockHitResult(Vec3.atCenterOf(pos), face, pos, false);
        InteractionResult r = mc.gameMode.useItemOn(mc.player, InteractionHand.MAIN_HAND, hit);
        if (r.consumesAction()) {
            p.swing(InteractionHand.MAIN_HAND);
            result = "used";
        } else {
            result = "not_used";
        }
        return true;
    }

    private boolean runPlace() {
        BlockPos support = readPos(act, "pos");
        if (support == null || mc.gameMode == null) {
            result = "bad_args";
            return true;
        }
        Player p = mc.player;
        Direction face = readFace(act);
        Vec3 c = Vec3.atCenterOf(support);
        if (p.getEyePosition().distanceTo(c) > 5.0D) {
            result = "too_far";
            return true;
        }
        Vec3 hitPos = c.add(face.getStepX() * 0.5D, face.getStepY() * 0.5D, face.getStepZ() * 0.5D);
        BlockHitResult hit = new BlockHitResult(hitPos, face, support, false);
        InteractionResult r = mc.gameMode.useItemOn(mc.player, InteractionHand.MAIN_HAND, hit);
        if (r.consumesAction()) {
            p.swing(InteractionHand.MAIN_HAND);
            result = "placed";
        } else {
            result = "not_placed";
        }
        return true;
    }

    private void abortDig() {
        if (digStarted && mc.gameMode != null) {
            mc.gameMode.stopDestroyBlock();
        }
        digStarted = false;
        digPos = null;
    }

    private void releaseUse() {
        if (useHeld) {
            mc.options.keyUse.setDown(false);
            useHeld = false;
        }
    }

    /* ======================================================================
     * OBSERVATION
     * ====================================================================== */

    public JsonObject observe() {
        if (mc.player == null || mc.level == null) {
            return error("no_player");
        }
        Player p = mc.player;
        JsonObject o = new JsonObject();
        o.addProperty("paused", mc.isPaused());
        o.addProperty("game_time", mc.level.getGameTime());
        o.addProperty("day_time", mc.level.getDayTime() % 24000L);
        o.addProperty("raining", mc.level.isRaining());
        o.addProperty("dimension", mc.level.dimension().location().toString());

        JsonObject pl = new JsonObject();
        Vec3 v = p.getDeltaMovement();
        pl.addProperty("x", p.getX());
        pl.addProperty("y", p.getY());
        pl.addProperty("z", p.getZ());
        pl.addProperty("vx", v.x);
        pl.addProperty("vy", v.y);
        pl.addProperty("vz", v.z);
        pl.addProperty("yaw", p.getYRot());
        pl.addProperty("pitch", p.getXRot());
        pl.addProperty("health", p.getHealth());
        pl.addProperty("max_health", p.getMaxHealth());
        pl.addProperty("food", p.getFoodData().getFoodLevel());
        pl.addProperty("saturation", p.getFoodData().getSaturationLevel());
        pl.addProperty("air", p.getAirSupply());
        pl.addProperty("max_air", p.getMaxAirSupply());
        pl.addProperty("on_ground", p.onGround());
        pl.addProperty("h_collision", p.horizontalCollision);
        pl.addProperty("in_water", p.isInWater());
        pl.addProperty("underwater", p.isUnderWater());
        pl.addProperty("in_lava", p.isInLava());
        pl.addProperty("on_fire", p.isOnFire());
        pl.addProperty("fall_distance", p.fallDistance);
        pl.addProperty("selected", p.getInventory().selected);
        pl.addProperty("dead", p.isDeadOrDying());
        o.add("player", pl);

        o.add("inventory", inventory(p));
        o.add("menu", menu(p));
        o.add("grid", grid(p));
        o.add("entities", entities(p));
        o.add("target", target(p));
        return o;
    }

    private JsonArray inventory(Player p) {
        JsonArray arr = new JsonArray();
        int n = p.getInventory().getContainerSize();
        for (int i = 0; i < n; i++) {
            ItemStack s = p.getInventory().getItem(i);
            if (s.isEmpty()) {
                continue;
            }
            JsonObject e = new JsonObject();
            e.addProperty("slot", i);
            e.addProperty("id", BuiltInRegistries.ITEM.getKey(s.getItem()).toString());
            e.addProperty("count", s.getCount());
            e.addProperty("damage", s.getDamageValue());
            e.addProperty("max_damage", s.getMaxDamage());
            arr.add(e);
        }
        return arr;
    }

    private JsonObject menu(Player p) {
        JsonObject m = new JsonObject();
        AbstractContainerMenu cm = p.containerMenu;
        String kind = "inventory";
        if (cm != null && cm != p.inventoryMenu) {
            if (cm instanceof CraftingMenu) {
                kind = "crafting";
            } else if (cm instanceof AbstractFurnaceMenu) {
                kind = "furnace";
            } else {
                kind = "other";
            }
        }
        m.addProperty("type", kind);
        JsonArray slots = new JsonArray();
        if (cm != null) {
            m.addProperty("id", cm.containerId);
            for (Slot s : cm.slots) {
                ItemStack st = s.getItem();
                if (st.isEmpty()) {
                    slots.add("");
                } else {
                    slots.add(BuiltInRegistries.ITEM.getKey(st.getItem()) + "*" + st.getCount());
                }
            }
            ItemStack cursor = cm.getCarried();
            m.addProperty("cursor", cursor.isEmpty() ? ""
                    : BuiltInRegistries.ITEM.getKey(cursor.getItem()) + "*" + cursor.getCount());
        }
        m.add("slots", slots);
        return m;
    }

    private JsonObject grid(Player p) {
        BlockPos o = p.blockPosition();
        Map<BlockState, Integer> index = new HashMap<>();
        List<String> names = new ArrayList<>();
        List<Integer> flags = new ArrayList<>();
        JsonArray data = new JsonArray();
        BlockPos.MutableBlockPos mp = new BlockPos.MutableBlockPos();
        for (int dx = -R; dx <= R; dx++) {
            for (int dy = YMIN; dy <= YMAX; dy++) {
                for (int dz = -R; dz <= R; dz++) {
                    mp.set(o.getX() + dx, o.getY() + dy, o.getZ() + dz);
                    BlockState st = mc.level.getBlockState(mp);
                    Integer id = index.get(st);
                    if (id == null) {
                        id = names.size();
                        index.put(st, id);
                        names.add(BuiltInRegistries.BLOCK.getKey(st.getBlock()).toString());
                        flags.add(classify(st, mp));
                    }
                    data.add(id);
                }
            }
        }
        JsonObject g = new JsonObject();
        g.addProperty("r", R);
        g.addProperty("ymin", YMIN);
        g.addProperty("ymax", YMAX);
        g.addProperty("ox", o.getX());
        g.addProperty("oy", o.getY());
        g.addProperty("oz", o.getZ());
        JsonArray pal = new JsonArray();
        for (String n : names) {
            pal.add(n);
        }
        JsonArray fl = new JsonArray();
        for (Integer f : flags) {
            fl.add(f);
        }
        g.add("pal", pal);
        g.add("fl", fl);
        g.add("d", data);
        return g;
    }

    /** 0 = passable, 1 = solid, 2 = water, 3 = lava. */
    private int classify(BlockState st, BlockPos pos) {
        if (!st.getCollisionShape(mc.level, pos).isEmpty()) {
            return 1;
        }
        if (!st.getFluidState().isEmpty()) {
            if (st.getFluidState().is(FluidTags.WATER)) {
                return 2;
            }
            if (st.getFluidState().is(FluidTags.LAVA)) {
                return 3;
            }
        }
        return 0;
    }

    private JsonArray entities(Player p) {
        JsonArray arr = new JsonArray();
        List<Entity> list = new ArrayList<>(mc.level.getEntities(p, p.getBoundingBox().inflate(ENTITY_RADIUS), e -> true));
        list.sort(Comparator.comparingDouble(e -> e.distanceToSqr(p)));
        int count = 0;
        for (Entity e : list) {
            if (count++ >= 64) {
                break;
            }
            JsonObject j = new JsonObject();
            j.addProperty("id", e.getId());
            j.addProperty("type", BuiltInRegistries.ENTITY_TYPE.getKey(e.getType()).toString());
            j.addProperty("x", e.getX());
            j.addProperty("y", e.getY());
            j.addProperty("z", e.getZ());
            j.addProperty("hostile", e instanceof Enemy);
            j.addProperty("player", e instanceof Player);
            if (e instanceof LivingEntity le) {
                j.addProperty("health", le.getHealth());
            }
            if (e instanceof ItemEntity ie) {
                j.addProperty("item", BuiltInRegistries.ITEM.getKey(ie.getItem().getItem()).toString());
                j.addProperty("count", ie.getItem().getCount());
            }
            arr.add(j);
        }
        return arr;
    }

    private JsonObject target(Player p) {
        JsonObject t = new JsonObject();
        HitResult r = p.pick(5.0D, 0.0F, false);
        if (r instanceof BlockHitResult bh && r.getType() == HitResult.Type.BLOCK) {
            BlockPos pos = bh.getBlockPos();
            t.addProperty("hit", true);
            t.addProperty("x", pos.getX());
            t.addProperty("y", pos.getY());
            t.addProperty("z", pos.getZ());
            t.addProperty("block", BuiltInRegistries.BLOCK.getKey(mc.level.getBlockState(pos).getBlock()).toString());
        } else {
            t.addProperty("hit", false);
        }
        return t;
    }

    /* ======================================================================
     * SCAN (long-range search for blocks by name fragment)
     * ====================================================================== */

    public JsonObject scan(List<String> fragments, int radius, int vertical, int max) {
        if (mc.player == null || mc.level == null) {
            return error("no_player");
        }
        BlockPos o = mc.player.blockPosition();
        Map<Block, Boolean> cache = new HashMap<>();
        BlockPos.MutableBlockPos mp = new BlockPos.MutableBlockPos();
        List<Object[]> found = new ArrayList<>();
        for (int dx = -radius; dx <= radius; dx++) {
            for (int dz = -radius; dz <= radius; dz++) {
                for (int dy = -vertical; dy <= vertical; dy++) {
                    mp.set(o.getX() + dx, o.getY() + dy, o.getZ() + dz);
                    BlockState st = mc.level.getBlockState(mp);
                    if (st.isAir()) {
                        continue;
                    }
                    Block b = st.getBlock();
                    Boolean match = cache.get(b);
                    String name = null;
                    if (match == null) {
                        name = BuiltInRegistries.BLOCK.getKey(b).toString();
                        boolean m = false;
                        for (String f : fragments) {
                            // "=minecraft:stone" matches exactly, anything else is a substring match
                            if (f.startsWith("=") ? name.equals(f.substring(1)) : name.contains(f)) {
                                m = true;
                                break;
                            }
                        }
                        cache.put(b, m);
                        match = m;
                    }
                    if (match) {
                        if (name == null) {
                            name = BuiltInRegistries.BLOCK.getKey(b).toString();
                        }
                        found.add(new Object[]{dx * dx + dy * dy + dz * dz, mp.getX(), mp.getY(), mp.getZ(), name});
                    }
                }
            }
        }
        found.sort(Comparator.comparingInt(a -> (Integer) a[0]));
        JsonArray arr = new JsonArray();
        for (int i = 0; i < Math.min(max, found.size()); i++) {
            Object[] f = found.get(i);
            JsonObject j = new JsonObject();
            j.addProperty("x", (Integer) f[1]);
            j.addProperty("y", (Integer) f[2]);
            j.addProperty("z", (Integer) f[3]);
            j.addProperty("block", (String) f[4]);
            arr.add(j);
        }
        JsonObject out = new JsonObject();
        out.add("blocks", arr);
        out.addProperty("total", found.size());
        return out;
    }

    /* ======================================================================
     * HELPERS
     * ====================================================================== */

    public static JsonObject error(String msg) {
        JsonObject e = new JsonObject();
        e.addProperty("error", msg);
        return e;
    }

    private static float wrap(float d) {
        d = d % 360.0F;
        if (d >= 180.0F) {
            d -= 360.0F;
        }
        if (d < -180.0F) {
            d += 360.0F;
        }
        return d;
    }

    private static int num(JsonObject o, String k, int def) {
        return o.has(k) && !o.get(k).isJsonNull() ? o.get(k).getAsInt() : def;
    }

    private static double num(JsonObject o, String k, double def) {
        return o.has(k) && !o.get(k).isJsonNull() ? o.get(k).getAsDouble() : def;
    }

    private static boolean bool(JsonObject o, String k) {
        return o.has(k) && !o.get(k).isJsonNull() && o.get(k).getAsBoolean();
    }

    private static String str(JsonObject o, String k, String def) {
        return o.has(k) && !o.get(k).isJsonNull() ? o.get(k).getAsString() : def;
    }

    private static BlockPos readPos(JsonObject o, String k) {
        if (!o.has(k) || !o.get(k).isJsonArray()) {
            return null;
        }
        JsonArray a = o.getAsJsonArray(k);
        if (a.size() < 3) {
            return null;
        }
        return new BlockPos(a.get(0).getAsInt(), a.get(1).getAsInt(), a.get(2).getAsInt());
    }

    private static Direction readFace(JsonObject o) {
        Direction d = Direction.byName(str(o, "face", "up"));
        return d == null ? Direction.UP : d;
    }
}
