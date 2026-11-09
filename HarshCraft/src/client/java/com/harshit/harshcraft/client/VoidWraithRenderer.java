package com.harshit.harshcraft.client;

import com.harshit.harshcraft.VoidWraithEntity;

import net.minecraft.client.renderer.entity.EntityRenderer;
import net.minecraft.client.renderer.entity.EntityRendererProvider;
import net.minecraft.resources.ResourceLocation;

public class VoidWraithRenderer extends EntityRenderer<VoidWraithEntity> {

    private static final ResourceLocation TEXTURE =
            ResourceLocation.fromNamespaceAndPath(
                    "harshcraft",
                    "textures/entity/void_wraith.png"
            );

    public VoidWraithRenderer(
            EntityRendererProvider.Context context
    ) {
        super(context);
        this.shadowRadius = 0.5F;
    }

    @Override
    public ResourceLocation getTextureLocation(
            VoidWraithEntity entity
    ) {
        return TEXTURE;
    }
}