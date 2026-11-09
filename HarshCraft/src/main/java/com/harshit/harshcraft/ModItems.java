package com.harshit.harshcraft;

import net.fabricmc.fabric.api.itemgroup.v1.ItemGroupEvents;
import net.minecraft.core.Registry;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.item.CreativeModeTabs;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.SwordItem;
import net.minecraft.world.item.Tiers;

public class ModItems {

    public static final Item VOID_SHARD = Registry.register(
            BuiltInRegistries.ITEM,
            ResourceLocation.fromNamespaceAndPath(
                    HarshCraft.MOD_ID,
                    "void_shard"
            ),
            new VoidShardItem(new Item.Properties())
    );

    public static final Item VOID_SWORD = Registry.register(
            BuiltInRegistries.ITEM,
            ResourceLocation.fromNamespaceAndPath(
                    HarshCraft.MOD_ID,
                    "void_sword"
            ),
            new VoidSwordItem(
                    new Item.Properties()
                            .attributes(
                                    SwordItem.createAttributes(
                                            Tiers.DIAMOND,
                                            4,
                                            -2.4F
                                    )
                            )
            )
    );

    public static final Item TELEPORT_COOLDOWN_TOKEN = Registry.register(
            BuiltInRegistries.ITEM,
            ResourceLocation.fromNamespaceAndPath(
                    HarshCraft.MOD_ID,
                    "teleport_cooldown_token"
            ),
            new Item(new Item.Properties())
    );

    public static final Item SNIPER_COOLDOWN_TOKEN = Registry.register(
            BuiltInRegistries.ITEM,
            ResourceLocation.fromNamespaceAndPath(
                    HarshCraft.MOD_ID,
                    "sniper_cooldown_token"
            ),
            new Item(new Item.Properties())
    );

    public static void registerModItems() {

        HarshCraft.LOGGER.info(
                "Registering Mod Items for " + HarshCraft.MOD_ID
        );

        // Void Shard → Ingredients tab
        ItemGroupEvents.modifyEntriesEvent(CreativeModeTabs.INGREDIENTS)
                .register(entries -> entries.accept(VOID_SHARD));

        // Void Sword → Combat tab
        ItemGroupEvents.modifyEntriesEvent(CreativeModeTabs.COMBAT)
                .register(entries -> entries.accept(VOID_SWORD));
    }
}