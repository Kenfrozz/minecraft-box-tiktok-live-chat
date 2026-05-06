package com.kenfroz.tiktokbox;

import org.bukkit.Bukkit;
import org.bukkit.Material;
import org.bukkit.World;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.FileConfiguration;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

public class ArenaConfig {
    public final World world;
    public final int minX, minY, minZ, maxX, maxY, maxZ;
    public final int sizeX, sizeY, sizeZ;
    public final Material wallMaterial;
    public final List<TierDefinition> tiers;
    public final double blockReach, entityReach;
    public final double blockBreakSpeed, miningEfficiency;
    public final int hasteAmplifier;
    public final int fastPlaceRadius;
    public final boolean autoConvertPlaced;
    public final int winSeconds;
    public final int scanIntervalTicks;
    public final Map<String, TntTier> tntTiers;
    public final int creeperCount;
    public final int creeperWalkTicks;
    public final int penaltyPrisonX, penaltyPrisonY, penaltyPrisonZ, penaltyPrisonTicks;
    public final int penaltyGauntletX, penaltyGauntletY, penaltyGauntletZ;
    public final int penaltyGauntletSize, penaltyGauntletTicks, penaltyGauntletMobCount;
    public final boolean botAutoStart;
    public final String botDefaultType;
    public final int botDefaultBps;
    public final String botDefaultName;
    public final boolean botGlowing;

    public record TntTier(float power, boolean fire) {}

    public ArenaConfig(FileConfiguration cfg) {
        String worldName = cfg.getString("arena.world", "world");
        this.world = Bukkit.getWorld(worldName);
        if (this.world == null) {
            throw new IllegalStateException("Dunya bulunamadi: " + worldName);
        }

        ConfigurationSection min = cfg.getConfigurationSection("arena.inner_min");
        ConfigurationSection max = cfg.getConfigurationSection("arena.inner_max");
        this.minX = min.getInt("x"); this.minY = min.getInt("y"); this.minZ = min.getInt("z");
        this.maxX = max.getInt("x"); this.maxY = max.getInt("y"); this.maxZ = max.getInt("z");
        this.sizeX = maxX - minX + 1;
        this.sizeY = maxY - minY + 1;
        this.sizeZ = maxZ - minZ + 1;

        this.wallMaterial = Material.matchMaterial(cfg.getString("arena.wall_material", "BEDROCK"));

        this.tiers = new ArrayList<>();
        for (Map<?, ?> t : cfg.getMapList("arena.tiers")) {
            String name = String.valueOf(t.get("name"));
            int yMin = ((Number) t.get("y_min")).intValue();
            int yMax = ((Number) t.get("y_max")).intValue();
            Material block = Material.matchMaterial(String.valueOf(t.get("block")));
            tiers.add(new TierDefinition(name, yMin, yMax, block));
        }

        this.blockReach = cfg.getDouble("player.block_reach", 9.0);
        this.entityReach = cfg.getDouble("player.entity_reach", 6.0);
        this.blockBreakSpeed = cfg.getDouble("player.block_break_speed", 5.0);
        this.miningEfficiency = cfg.getDouble("player.mining_efficiency", 5.0);
        this.hasteAmplifier = cfg.getInt("player.haste_amplifier", 4);
        this.fastPlaceRadius = cfg.getInt("player.fast_place_radius", 2);
        this.autoConvertPlaced = cfg.getBoolean("arena.auto_convert_placed", true);
        this.winSeconds = cfg.getInt("countdown.win_seconds", 10);
        this.scanIntervalTicks = cfg.getInt("monitor.scan_interval_ticks", 10);

        this.creeperCount = cfg.getInt("tnt.creeper.count", 6);
        this.creeperWalkTicks = cfg.getInt("tnt.creeper.walk_ticks", 60);

        this.penaltyPrisonX = cfg.getInt("penalty.prison.x", 50);
        this.penaltyPrisonY = cfg.getInt("penalty.prison.y", 200);
        this.penaltyPrisonZ = cfg.getInt("penalty.prison.z", 50);
        this.penaltyPrisonTicks = cfg.getInt("penalty.prison.duration_ticks", 200);
        this.penaltyGauntletX = cfg.getInt("penalty.gauntlet.x", 100);
        this.penaltyGauntletY = cfg.getInt("penalty.gauntlet.y", 80);
        this.penaltyGauntletZ = cfg.getInt("penalty.gauntlet.z", 100);
        this.penaltyGauntletSize = cfg.getInt("penalty.gauntlet.size", 14);
        this.penaltyGauntletTicks = cfg.getInt("penalty.gauntlet.duration_ticks", 600);
        this.penaltyGauntletMobCount = cfg.getInt("penalty.gauntlet.mob_count", 4);

        this.botAutoStart = cfg.getBoolean("bot.auto_start", true);
        this.botDefaultType = cfg.getString("bot.default_type", "enderman");
        this.botDefaultBps = cfg.getInt("bot.default_bps", 2);
        this.botDefaultName = cfg.getString("bot.default_name", "Usta");
        this.botGlowing = cfg.getBoolean("bot.glowing", false);

        this.tntTiers = new java.util.HashMap<>();
        ConfigurationSection tntSec = cfg.getConfigurationSection("tnt.tiers");
        if (tntSec != null) {
            for (String key : tntSec.getKeys(false)) {
                float p = (float) tntSec.getDouble(key + ".power", 4.0);
                boolean f = tntSec.getBoolean(key + ".fire", false);
                tntTiers.put(key.toLowerCase(), new TntTier(p, f));
            }
        }
    }

    public int totalBlocks() {
        int total = 0;
        for (TierDefinition t : tiers) total += sizeX * sizeZ * (t.yMax() - t.yMin() + 1);
        return total == 0 ? sizeX * sizeY * sizeZ : total;
    }

    public TierDefinition tierForY(int y) {
        for (TierDefinition t : tiers) if (y >= t.yMin() && y <= t.yMax()) return t;
        return null;
    }

    public boolean isInsideInner(int x, int y, int z) {
        return x >= minX && x <= maxX && y >= minY && y <= maxY && z >= minZ && z <= maxZ;
    }
}
