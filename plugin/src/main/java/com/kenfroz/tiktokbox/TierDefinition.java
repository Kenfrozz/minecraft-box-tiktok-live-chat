package com.kenfroz.tiktokbox;

import org.bukkit.Material;

public record TierDefinition(String name, int yMin, int yMax, Material block) {
    public int volume(int xSize, int zSize) {
        return xSize * zSize * (yMax - yMin + 1);
    }
}
