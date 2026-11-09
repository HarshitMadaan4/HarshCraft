package com.harshit.harshcraft;

import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.ai.attributes.AttributeSupplier;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.entity.monster.Monster;
import net.minecraft.world.level.Level;

public class VoidWraithEntity extends Monster {

    public VoidWraithEntity(
            EntityType<? extends Monster> entityType,
            Level level
    ) {
        super(entityType, level);
    }

    public static AttributeSupplier.Builder createAttributes() {

        return Monster.createMonsterAttributes()
                .add(Attributes.MAX_HEALTH, 30.0)
                .add(Attributes.MOVEMENT_SPEED, 0.30)
                .add(Attributes.FLYING_SPEED, 0.60)
                .add(Attributes.ATTACK_DAMAGE, 6.0)
                .add(Attributes.FOLLOW_RANGE, 32.0);
    }
}