package com.harshit.harshcraft.client;

import com.harshit.harshcraft.HarshCraft;
import com.harshit.harshcraft.ModEntities;
import com.harshit.harshcraft.ModItems;
import com.harshit.harshcraft.VoidSwordItem;
import com.harshit.harshcraft.ai.AIEnvironment;
import com.harshit.harshcraft.ai.AIHttpServer;

import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
import net.fabricmc.fabric.api.client.rendering.v1.EntityRendererRegistry;
import net.fabricmc.fabric.api.client.rendering.v1.HudRenderCallback;

import net.minecraft.client.DeltaTracker;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiGraphics;

import net.minecraft.core.particles.ParticleTypes;

import net.minecraft.world.item.ItemStack;
import net.minecraft.world.phys.Vec3;

public class HarshCraftClient
        implements ClientModInitializer {

    /*
     * ============================================================
     * VOID SWORD FOV
     * ============================================================
     */

    private static float currentZoom = 0.0F;

    private static final float ZOOM_SPEED = 0.08F;

    private static final float MAX_ZOOM = 0.35F;

    private static final ItemStack SNIPER_COOLDOWN_STACK =
            new ItemStack(
                    ModItems.SNIPER_COOLDOWN_TOKEN
            );

    /*
     * ============================================================
     * AI ENVIRONMENT
     * ============================================================
     *
     * IMPORTANT:
     *
     * This MUST be static/shared.
     *
     * HTTP server and client tick both use the same instance.
     */

    private static AIEnvironment aiEnvironment;

    private static AIHttpServer aiServer;

    /*
     * ============================================================
     * INITIALIZE
     * ============================================================
     */

    @Override
    public void onInitializeClient() {

        HarshCraft.LOGGER.info(
                "HarshCraft client initialized!"
        );

        /*
         * ========================================================
         * VOID WRAITH
         * ========================================================
         */

        EntityRendererRegistry.register(
                ModEntities.VOID_WRAITH,
                VoidWraithRenderer::new
        );

        /*
         * ========================================================
         * AI ENVIRONMENT
         * ========================================================
         */

        aiEnvironment =
                new AIEnvironment(
                        Minecraft.getInstance()
                );

        /*
         * ========================================================
         * HTTP SERVER
         * ========================================================
         */

        try {

            aiServer =
                    new AIHttpServer(
                            aiEnvironment,
                            Minecraft.getInstance()
                    );

            aiServer.start();

        } catch (Exception e) {

            HarshCraft.LOGGER.error(
                    "Failed to start AI HTTP server",
                    e
            );
        }

        /*
         * ========================================================
         * CLIENT TICK
         * ========================================================
         *
         * AI control happens here.
         */

        ClientTickEvents.END_CLIENT_TICK.register(
                HarshCraftClient::handleClientTick
        );

        /*
         * ========================================================
         * HUD
         * ========================================================
         */

        HudRenderCallback.EVENT.register(
                HarshCraftClient::renderCooldownHud
        );
    }

    /*
     * ============================================================
     * CLIENT TICK
     * ============================================================
     */
    public static void applyAIMovement() {
        if (aiEnvironment != null) {
            aiEnvironment.applyInput();
        }
    }
    private static void handleClientTick(
            Minecraft client
    ) {

        /*
         * ========================================================
         * NO PLAYER
         * ========================================================
         */

        if (client.player == null) {

            currentZoom = 0.0F;

            if (aiEnvironment != null) {
                aiEnvironment.stopAction();
            }

            return;
        }

        /*
         * ========================================================
         * PAUSED
         * ========================================================
         *
         * Do NOT let AI movement continue while paused.
         */

        if (client.isPaused()) {

            if (aiEnvironment != null) {
                aiEnvironment.stopAction();
            }

            return;
        }

        /*
         * ========================================================
         * AI CONTROL
         * ========================================================
         */

        if (aiEnvironment != null) {

            aiEnvironment.tick();
        }

        /*
         * ========================================================
         * VOID SWORD FOV
         * ========================================================
         */

        ItemStack stack =
                client.player.getMainHandItem();

        boolean charging = false;

        if (stack.getItem()
                instanceof VoidSwordItem
                && client.player.isUsingItem()
                && client.player.getUseItem()
                .is(stack.getItem())) {

            int useTime =
                    stack.getUseDuration(
                            client.player
                    )
                            - client.player
                            .getUseItemRemainingTicks();

            if (useTime >= 20) {

                charging = true;
            }
        }

        /*
         * Smooth zoom IN
         */

        if (charging) {

            currentZoom += ZOOM_SPEED;

            if (currentZoom > MAX_ZOOM) {

                currentZoom =
                        MAX_ZOOM;
            }

        } else {

            /*
             * Smooth zoom OUT
             */

            currentZoom -= ZOOM_SPEED;

            if (currentZoom < 0.0F) {

                currentZoom =
                        0.0F;
            }
        }

        /*
         * ========================================================
         * VOID SWORD AURA
         * ========================================================
         */

        spawnVoidSwordAura(client);
    }

    /*
     * ============================================================
     * VOID SWORD AURA
     * ============================================================
     */

    private static void spawnVoidSwordAura(
            Minecraft client
    ) {

        if (client.player == null
                || client.level == null) {

            return;
        }

        ItemStack stack =
                client.player.getMainHandItem();

        if (!(stack.getItem()
                instanceof VoidSwordItem)) {

            return;
        }

        Vec3 look =
                client.player
                        .getLookAngle()
                        .normalize();

        Vec3 right =
                look.cross(
                        new Vec3(
                                0.0D,
                                1.0D,
                                0.0D
                        )
                );

        if (right.lengthSqr() < 0.001D) {

            right =
                    new Vec3(
                            1.0D,
                            0.0D,
                            0.0D
                    );

        } else {

            right =
                    right.normalize();
        }

        Vec3 up =
                right.cross(look)
                        .normalize();

        Vec3 swordBase =
                client.player
                        .getEyePosition()
                        .add(
                                look.scale(
                                        0.45D
                                )
                        )
                        .add(
                                right.scale(
                                        0.35D
                                )
                        )
                        .add(
                                up.scale(
                                        -0.35D
                                )
                        );

        for (int i = 0; i < 3; i++) {

            double distance =
                    0.10D
                            + client.level.random
                            .nextDouble()
                            * 0.85D;

            double side =
                    (
                            client.level.random
                                    .nextDouble()
                                    - 0.5D
                    ) * 0.14D;

            double vertical =
                    (
                            client.level.random
                                    .nextDouble()
                                    - 0.5D
                    ) * 0.14D;

            Vec3 position =
                    swordBase
                            .add(
                                    look.scale(
                                            distance
                                    )
                            )
                            .add(
                                    right.scale(
                                            side
                                    )
                            )
                            .add(
                                    up.scale(
                                            vertical
                                    )
                            );

            client.level.addParticle(
                    ParticleTypes.SOUL_FIRE_FLAME,

                    position.x,
                    position.y,
                    position.z,

                    0.0D,
                    0.015D,
                    0.0D
            );

            if (client.level.random
                    .nextFloat() < 0.40F) {

                client.level.addParticle(
                        ParticleTypes.REVERSE_PORTAL,

                        position.x,
                        position.y,
                        position.z,

                        0.0D,
                        0.015D,
                        0.0D
                );
            }
        }
    }

    /*
     * ============================================================
     * COOLDOWN HUD
     * ============================================================
     */

    private static void renderCooldownHud(
            GuiGraphics graphics,
            DeltaTracker deltaTracker
    ) {

        Minecraft client =
                Minecraft.getInstance();

        if (client.player == null) {
            return;
        }

        if (!(client.player
                .getMainHandItem()
                .getItem()
                instanceof VoidSwordItem)) {

            return;
        }

        float cooldownProgress =
                client.player
                        .getCooldowns()
                        .getCooldownPercent(
                                ModItems.SNIPER_COOLDOWN_TOKEN,

                                deltaTracker
                                        .getGameTimeDeltaPartialTick(
                                                false
                                        )
                        );

        if (cooldownProgress <= 0.0F) {
            return;
        }

        float remainingSeconds =
                cooldownProgress * 20.0F;

        String text =
                String.format(
                        java.util.Locale.ROOT,
                        "VOID SHOT: %.1fs",
                        remainingSeconds
                );

        int screenWidth =
                client.getWindow()
                        .getGuiScaledWidth();

        int screenHeight =
                client.getWindow()
                        .getGuiScaledHeight();

        int x =
                screenWidth / 2;

        int y =
                screenHeight - 50;

        graphics.drawCenteredString(
                client.font,

                net.minecraft.network.chat
                        .Component
                        .literal(text),

                x,
                y,

                0xC080FF
        );
    }

    /*
     * ============================================================
     * FOV ACCESSOR
     * ============================================================
     */

    public static float getVoidSwordZoom() {

        return currentZoom;
    }
}