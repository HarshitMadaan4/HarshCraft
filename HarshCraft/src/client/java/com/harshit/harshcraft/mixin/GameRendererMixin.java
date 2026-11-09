package com.harshit.harshcraft.mixin;

import com.harshit.harshcraft.client.HarshCraftClient;
import net.minecraft.client.Camera;
import net.minecraft.client.renderer.GameRenderer;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

@Mixin(GameRenderer.class)
public class GameRendererMixin {

    @Inject(
            method = "getFov",
            at = @At("RETURN"),
            cancellable = true
    )
    private void modifyFov(
            Camera camera,
            float partialTick,
            boolean changingFov,
            CallbackInfoReturnable<Double> cir
    ) {

        double originalFov = cir.getReturnValue();

        float zoom = HarshCraftClient.getVoidSwordZoom();

        if (zoom > 0.0F) {
            double newFov = originalFov * (1.0D - zoom);
            cir.setReturnValue(newFov);
        }
    }
}