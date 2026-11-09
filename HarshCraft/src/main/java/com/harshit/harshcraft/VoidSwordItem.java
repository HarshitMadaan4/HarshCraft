package com.harshit.harshcraft;

import net.minecraft.core.BlockPos;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.sounds.SoundSource;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResultHolder;
import net.minecraft.world.effect.MobEffectInstance;
import net.minecraft.world.effect.MobEffects;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.SwordItem;
import net.minecraft.world.item.Tiers;
import net.minecraft.world.item.UseAnim;
import net.minecraft.world.level.ClipContext;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.HitResult;
import net.minecraft.world.phys.Vec3;

import java.util.Comparator;
import java.util.List;
import java.util.Optional;

public class VoidSwordItem extends SwordItem {

    /*
     * ============================================================
     * COOLDOWNS
     * ============================================================
     */

    private static final int TELEPORT_COOLDOWN = 20 * 10; // 10 sec
    private static final int SNIPER_COOLDOWN = 20 * 20;   // 20 sec

    /*
     * Hold for 1 second:
     *
     * < 20 ticks  -> teleport
     * >= 20 ticks -> sniper
     */
    private static final int CHARGE_TIME = 20;

    /*
     * Maximum sniper range.
     */
    private static final double SNIPER_RANGE = 100.0D;

    /*
     * Damage:
     *
     * 20 damage = 10 hearts
     */
    private static final float SNIPER_DAMAGE = 20.0F;


    public VoidSwordItem(Properties properties) {
        super(Tiers.DIAMOND, properties);
    }


    /*
     * ============================================================
     * BOW-LIKE USE ANIMATION
     * ============================================================
     */

    @Override
    public UseAnim getUseAnimation(ItemStack stack) {
        return UseAnim.BOW;
    }


    /*
     * ============================================================
     * STRENGTH I + SPEED II
     *
     * Also creates the constant Void aura.
     * ============================================================
     */

    @Override
    public void inventoryTick(
            ItemStack stack,
            Level level,
            Entity entity,
            int slot,
            boolean selected
    ) {
        super.inventoryTick(
                stack,
                level,
                entity,
                slot,
                selected
        );

        if (!(entity instanceof Player player)) {
            return;
        }

        /*
         * Only while the sword is in the MAIN HAND.
         */
        if (!player.getMainHandItem().is(this)) {
            return;
        }

        /*
         * ========================================================
         * STRENGTH I
         * ========================================================
         */

        if (!level.isClientSide()) {

            player.addEffect(
                    new MobEffectInstance(
                            MobEffects.DAMAGE_BOOST,
                            40,
                            0,
                            false,
                            false
                    )
            );

            /*
             * ====================================================
             * SPEED II
             * ====================================================
             */

            player.addEffect(
                    new MobEffectInstance(
                            MobEffects.MOVEMENT_SPEED,
                            40,
                            1,
                            false,
                            false
                    )
            );
        }

        /*
         * ========================================================
         * CONSTANT VOID / SHADOW AURA
         * ========================================================
         */

        if (level instanceof ServerLevel serverLevel) {

            Vec3 pos = player.position();

            /*
             * Dark portal particles around player.
             */
            serverLevel.sendParticles(
                    ParticleTypes.REVERSE_PORTAL,
                    pos.x,
                    pos.y + 1.0D,
                    pos.z,
                    3,
                    0.35D,
                    0.7D,
                    0.35D,
                    0.03D
            );

            /*
             * Additional purple particles.
             */
            if (level.getGameTime() % 4 == 0) {

                serverLevel.sendParticles(
                        ParticleTypes.PORTAL,
                        pos.x,
                        pos.y + 0.8D,
                        pos.z,
                        5,
                        0.45D,
                        0.8D,
                        0.45D,
                        0.08D
                );
            }
        }
    }


    /*
     * ============================================================
     * CHARGING PARTICLES
     *
     * Called every tick while right-click is held.
     * ============================================================
     */

    @Override
    public void onUseTick(
            Level level,
            LivingEntity entity,
            ItemStack stack,
            int remainingUseDuration
    ) {
        super.onUseTick(
                level,
                entity,
                stack,
                remainingUseDuration
        );

        if (!(entity instanceof Player player)) {
            return;
        }

        int elapsed =
                getUseDuration(stack, player)
                        - remainingUseDuration;

        /*
         * First second is teleport charging.
         *
         * Don't show sniper charging particles yet.
         */
        if (elapsed < CHARGE_TIME) {
            return;
        }

        /*
         * ========================================================
         * CHARGE PROGRESS
         *
         * 0.0 = just started sniper charge
         * 1.0 = fully charged
         *
         * Takes another second to reach full charge.
         * ========================================================
         */

        float charge =
                Math.min(
                        1.0F,
                        (elapsed - CHARGE_TIME) / 20.0F
                );

        /*
         * ========================================================
         * POSITION NEAR SWORD / HAND
         * ========================================================
         */

        Vec3 look =
                player.getLookAngle();

        Vec3 right =
                look.cross(
                        new Vec3(0.0D, 1.0D, 0.0D)
                );

        if (right.lengthSqr() < 0.001D) {
            right = new Vec3(1.0D, 0.0D, 0.0D);
        } else {
            right = right.normalize();
        }

        Vec3 particlePosition =
                player.getEyePosition()
                        .add(right.scale(0.35D))
                        .add(0.0D, -0.25D, 0.0D);


        /*
         * ========================================================
         * CHARGING PARTICLES
         * ========================================================
         */

        int particleCount =
                1 + (int) (charge * 5.0F);

        for (int i = 0; i < particleCount; i++) {

            double angle =
                    level.random.nextDouble()
                            * Math.PI * 2.0D;

            /*
             * Radius increases as charge increases.
             */
            double radius =
                    0.10D + charge * 0.35D;

            double x =
                    particlePosition.x
                            + Math.cos(angle) * radius;

            double y =
                    particlePosition.y
                            + level.random.nextGaussian()
                            * 0.08D;

            double z =
                    particlePosition.z
                            + Math.sin(angle) * radius;


            /*
             * Client side particle.
             */
            if (level.isClientSide()) {

                level.addParticle(
                        ParticleTypes.PORTAL,
                        x,
                        y,
                        z,
                        0.0D,
                        0.02D + charge * 0.04D,
                        0.0D
                );

            }

            /*
             * Server side particle.
             */
            else if (level instanceof ServerLevel serverLevel) {

                serverLevel.sendParticles(
                        ParticleTypes.PORTAL,
                        x,
                        y,
                        z,
                        1,
                        0.0D,
                        0.02D + charge * 0.04D,
                        0.0D,
                        0.0D
                );
            }
        }


        /*
         * ========================================================
         * FULL CHARGE EFFECT
         * ========================================================
         */

        if (charge >= 1.0F
                && level.getGameTime() % 2 == 0) {

            if (level.isClientSide()) {

                level.addParticle(
                        ParticleTypes.REVERSE_PORTAL,
                        particlePosition.x,
                        particlePosition.y,
                        particlePosition.z,
                        0.0D,
                        0.08D,
                        0.0D
                );

            } else if (level instanceof ServerLevel serverLevel) {

                serverLevel.sendParticles(
                        ParticleTypes.REVERSE_PORTAL,
                        particlePosition.x,
                        particlePosition.y,
                        particlePosition.z,
                        3,
                        0.12D,
                        0.12D,
                        0.12D,
                        0.04D
                );
            }
        }
    }


    /*
     * ============================================================
     * RIGHT CLICK
     *
     * Starts charging.
     *
     * IMPORTANT:
     * We do NOT check either cooldown here.
     *
     * Teleport and sniper are independent.
     * ============================================================
     */

    @Override
    public InteractionResultHolder<ItemStack> use(
            Level level,
            Player player,
            InteractionHand hand
    ) {

        ItemStack stack =
                player.getItemInHand(hand);

        player.startUsingItem(hand);

        return InteractionResultHolder.consume(stack);
    }


    /*
     * ============================================================
     * RIGHT CLICK RELEASE
     *
     * < 20 ticks  -> TELEPORT
     * >= 20 ticks -> SNIPER
     * ============================================================
     */

    @Override
    public void releaseUsing(
            ItemStack stack,
            Level level,
            LivingEntity entity,
            int timeLeft
    ) {

        if (!(entity instanceof ServerPlayer player)) {
            return;
        }

        int elapsed =
                getUseDuration(stack, entity)
                        - timeLeft;


        /*
         * ========================================================
         * SHORT CLICK -> TELEPORT
         * ========================================================
         */

        if (elapsed < CHARGE_TIME) {

            /*
             * ONLY check teleport cooldown.
             */
            if (!player.getCooldowns().isOnCooldown(
                    ModItems.TELEPORT_COOLDOWN_TOKEN
            )) {

                teleportPlayer(player);

                /*
                 * ONLY teleport cooldown.
                 */
                player.getCooldowns().addCooldown(
                        ModItems.TELEPORT_COOLDOWN_TOKEN,
                        TELEPORT_COOLDOWN
                );
            }

            return;
        }


        /*
         * ========================================================
         * LONG CLICK -> SNIPER
         * ========================================================
         */

        /*
         * ONLY check sniper cooldown.
         *
         * Teleport cooldown does NOT matter here.
         */
        if (!player.getCooldowns().isOnCooldown(
                ModItems.SNIPER_COOLDOWN_TOKEN
        )) {

            fireSniperShot(player);

            /*
             * ONLY sniper cooldown.
             */
            player.getCooldowns().addCooldown(
                    ModItems.SNIPER_COOLDOWN_TOKEN,
                    SNIPER_COOLDOWN
            );
        }
    }


    /*
     * ============================================================
     * TELEPORT
     * ============================================================
     */

    private void teleportPlayer(
            ServerPlayer player
    ) {

        Level level =
                player.level();

        /*
         * Raycast 64 blocks.
         */
        BlockHitResult hit =
                (BlockHitResult) player.pick(
                        64.0D,
                        1.0F,
                        false
                );

        if (hit.getType()
                != HitResult.Type.BLOCK) {

            return;
        }

        /*
         * Put player on the other side
         * of the block they're looking at.
         */
        BlockPos targetBlock =
                hit.getBlockPos()
                        .relative(hit.getDirection());

        /*
         * Don't teleport into a solid block.
         */
        if (!level.getBlockState(targetBlock).isAir()) {
            return;
        }

        double x =
                targetBlock.getX() + 0.5D;

        double y =
                targetBlock.getY();

        double z =
                targetBlock.getZ() + 0.5D;


        player.teleportTo(
                x,
                y,
                z
        );


        /*
         * Teleport particles.
         */
        createTeleportParticles(
                (ServerLevel) level,
                new Vec3(x, y, z)
        );


        /*
         * Teleport sound.
         */
        level.playSound(
                null,
                player.blockPosition(),
                SoundEvents.ENDERMAN_TELEPORT,
                SoundSource.PLAYERS,
                1.0F,
                1.0F
        );
    }


    /*
     * ============================================================
     * SNIPER SHOT
     *
     * 100 block range.
     * Pierces mobs.
     * Stops at blocks.
     * ============================================================
     */

    private void fireSniperShot(
            ServerPlayer player
    ) {

        ServerLevel level =
                player.serverLevel();


        /*
         * ========================================================
         * START
         * ========================================================
         */

        Vec3 start =
                player.getEyePosition();


        /*
         * EXACT LOOK DIRECTION.
         */
        Vec3 direction =
                player.getLookAngle();


        /*
         * ========================================================
         * END OF MAXIMUM RANGE
         * ========================================================
         */

        Vec3 maxEnd =
                start.add(
                        direction.scale(
                                SNIPER_RANGE
                        )
                );


        /*
         * ========================================================
         * BLOCK RAYCAST
         *
         * This determines exactly where
         * the beam stops.
         * ========================================================
         */

        BlockHitResult blockHit =
                level.clip(
                        new ClipContext(
                                start,
                                maxEnd,
                                ClipContext.Block.COLLIDER,
                                ClipContext.Fluid.NONE,
                                player
                        )
                );


        Vec3 hitPosition =
                blockHit.getType()
                        == HitResult.Type.BLOCK
                        ? blockHit.getLocation()
                        : maxEnd;


        /*
         * ========================================================
         * ACTUAL BEAM DISTANCE
         * ========================================================
         */

        double beamDistance =
                start.distanceTo(
                        hitPosition
                );


        /*
         * ========================================================
         * PURPLE BEAM PARTICLES
         *
         * Particles follow EXACTLY the same
         * trajectory as the damage ray.
         * ========================================================
         */

        int particleCount =
                Math.max(
                        40,
                        (int) (beamDistance * 3.0D)
                );


        for (int i = 0;
             i < particleCount;
             i++) {

            double progress =
                    i / (double) particleCount;


            Vec3 position =
                    start.lerp(
                            hitPosition,
                            progress
                    );


            level.sendParticles(
                    ParticleTypes.PORTAL,
                    position.x,
                    position.y,
                    position.z,
                    1,
                    0.0D,
                    0.0D,
                    0.0D,
                    0.0D
            );
        }


        /*
         * ========================================================
         * FIND ALL MOBS NEAR THE BEAM
         * ========================================================
         */

        double maxDistance =
                beamDistance;


        List<LivingEntity> targets =
                level.getEntitiesOfClass(
                        LivingEntity.class,

                        player.getBoundingBox()
                                .expandTowards(
                                        direction.scale(
                                                maxDistance
                                        )
                                )
                                .inflate(3.0D),

                        target ->
                                target != player
                                        && target.isAlive()
                );


        /*
         * ========================================================
         * SORT BY DISTANCE
         *
         * Closest mob gets hit first.
         * ========================================================
         */

        targets.sort(
                Comparator.comparingDouble(
                        target ->
                                start.distanceToSqr(
                                        target.getBoundingBox()
                                                .getCenter()
                                )
                )
        );


        /*
         * ========================================================
         * HITBOX INTERSECTION
         *
         * This fixes the problem where aiming at
         * legs/head/etc. could miss.
         * ========================================================
         */

        for (LivingEntity target : targets) {

            Optional<Vec3> intersection =
                    target.getBoundingBox()
                            .clip(
                                    start,
                                    hitPosition
                            );


            /*
             * Beam doesn't intersect this mob.
             */
            if (intersection.isEmpty()) {
                continue;
            }


            Vec3 hitPoint =
                    intersection.get();


            /*
             * Don't damage entities beyond
             * the block that stopped the beam.
             */
            if (start.distanceToSqr(hitPoint)
                    > start.distanceToSqr(hitPosition)) {

                continue;
            }


            /*
             * ====================================================
             * DAMAGE
             *
             * 20 = 10 hearts.
             * ====================================================
             */

            target.hurt(
                    level.damageSources()
                            .playerAttack(player),
                    SNIPER_DAMAGE
            );


            /*
             * ====================================================
             * PIERCING
             *
             * IMPORTANT:
             *
             * NO break here.
             *
             * The shot continues through this mob
             * and can hit another mob.
             * ====================================================
             */
        }


        /*
         * ========================================================
         * IMPACT PARTICLES
         * ========================================================
         */

        level.sendParticles(
                ParticleTypes.REVERSE_PORTAL,
                hitPosition.x,
                hitPosition.y,
                hitPosition.z,
                50,
                0.5D,
                0.5D,
                0.5D,
                0.15D
        );


        level.sendParticles(
                ParticleTypes.PORTAL,
                hitPosition.x,
                hitPosition.y,
                hitPosition.z,
                80,
                0.5D,
                0.5D,
                0.5D,
                0.2D
        );


        /*
         * ========================================================
         * SOUND
         * ========================================================
         */

        level.playSound(
                null,
                player.blockPosition(),
                SoundEvents.BEACON_POWER_SELECT,
                SoundSource.PLAYERS,
                1.0F,
                0.5F
        );
    }


    /*
     * ============================================================
     * TELEPORT PARTICLES
     * ============================================================
     */

    private void createTeleportParticles(
            ServerLevel level,
            Vec3 position
    ) {

        level.sendParticles(
                ParticleTypes.REVERSE_PORTAL,
                position.x,
                position.y + 1.0D,
                position.z,
                50,
                0.5D,
                1.0D,
                0.5D,
                0.2D
        );


        level.sendParticles(
                ParticleTypes.PORTAL,
                position.x,
                position.y + 1.0D,
                position.z,
                50,
                0.5D,
                1.0D,
                0.5D,
                0.2D
        );
    }


    /*
     * ============================================================
     * MAXIMUM USE DURATION
     *
     * Allows the player to hold right-click indefinitely.
     * ============================================================
     */

    @Override
    public int getUseDuration(
            ItemStack stack,
            LivingEntity entity
    ) {
        return 72000;
    }
}