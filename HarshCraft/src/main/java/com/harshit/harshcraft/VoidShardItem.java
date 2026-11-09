package com.harshit.harshcraft;

import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResultHolder;
import net.minecraft.world.effect.MobEffectInstance;
import net.minecraft.world.effect.MobEffects;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.Level;

public class VoidShardItem extends Item {

    public VoidShardItem(Properties properties) {
        super(properties);
    }

    @Override
    public InteractionResultHolder<ItemStack> use(
            Level level,
            Player player,
            InteractionHand hand
    ) {

        ItemStack stack = player.getItemInHand(hand);

        // Only run the ability on the server
        if (!level.isClientSide()) {

            // Give the player Speed II for 10 seconds
            player.addEffect(
                    new MobEffectInstance(
                            MobEffects.MOVEMENT_SPEED,
                            200,
                            1
                    )
            );

            // 5 second cooldown
            player.getCooldowns().addCooldown(this, 100);
        }

        return InteractionResultHolder.sidedSuccess(
                stack,
                level.isClientSide()
        );
    }
}