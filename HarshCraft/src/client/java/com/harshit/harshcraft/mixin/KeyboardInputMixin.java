package com.harshit.harshcraft.mixin;

import com.harshit.harshcraft.client.HarshCraftClient;
import net.minecraft.client.player.KeyboardInput;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(KeyboardInput.class)
public class KeyboardInputMixin {

    @Inject(
            method = "tick",
            at = @At("RETURN")
    )
    private void harshcraft$applyAIMovement(CallbackInfo ci) {
        HarshCraftClient.applyAIMovement();
    }
}