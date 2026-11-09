package com.harshit.harshcraft;

import net.fabricmc.fabric.api.object.builder.v1.entity.FabricDefaultAttributeRegistry;

import net.minecraft.core.Registry;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.MobCategory;

public class ModEntities {

    public static final EntityType<VoidWraithEntity> VOID_WRAITH =
            Registry.register(
                    BuiltInRegistries.ENTITY_TYPE,

                    ResourceLocation.fromNamespaceAndPath(
                            HarshCraft.MOD_ID,
                            "void_wraith"
                    ),

                    EntityType.Builder.of(
                                    VoidWraithEntity::new,
                                    MobCategory.MONSTER
                            )
                            .sized(0.9F, 1.8F)
                            .build(
                                    ResourceLocation.fromNamespaceAndPath(
                                            HarshCraft.MOD_ID,
                                            "void_wraith"
                                    ).toString()
                            )
            );

    public static void registerModEntities() {

        HarshCraft.LOGGER.info(
                "Registering Mod Entities for " + HarshCraft.MOD_ID
        );

        FabricDefaultAttributeRegistry.register(
                VOID_WRAITH,
                VoidWraithEntity.createAttributes()
        );
    }
}