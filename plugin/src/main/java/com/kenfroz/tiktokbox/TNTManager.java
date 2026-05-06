package com.kenfroz.tiktokbox;

import net.kyori.adventure.text.Component;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.block.Block;
import org.bukkit.entity.Creeper;
import org.bukkit.entity.Entity;
import org.bukkit.entity.EntityType;
import org.bukkit.entity.TNTPrimed;
import org.bukkit.event.entity.CreatureSpawnEvent;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.ExplosionPrimeEvent;
import org.bukkit.plugin.java.JavaPlugin;
import org.bukkit.scheduler.BukkitRunnable;

import java.util.Random;
import java.util.Set;

public class TNTManager implements Listener {
    private final JavaPlugin plugin;
    private final ArenaConfig config;
    private final Random rnd = new Random();

    public TNTManager(JavaPlugin plugin, ArenaConfig config) {
        this.plugin = plugin;
        this.config = config;
    }

    @EventHandler(priority = EventPriority.HIGH)
    public void onExplosionPrime(ExplosionPrimeEvent event) {
        Entity ent = event.getEntity();
        Set<String> tags = ent.getScoreboardTags();
        if (ent instanceof TNTPrimed tnt && tags.contains("box_creeper")) {
            event.setRadius(1.5f);
            event.setFire(false);
            Component name = tnt.customName();
            spawnCreeperHorde(tnt.getLocation(), name);
            return;
        }
        if (tags.contains("box_meteor")) {
            ArenaConfig.TntTier def = config.tntTiers.get("meteor");
            float power = def != null ? def.power() : 3.5f;
            event.setRadius(power);
            event.setFire(def != null && def.fire());
            destroyArenaBlocks(ent.getLocation(), power);
            return;
        }
        for (String tag : tags) {
            if (!tag.startsWith("box_")) continue;
            String tier = tag.substring(4).toLowerCase();
            ArenaConfig.TntTier def = config.tntTiers.get(tier);
            if (def != null) {
                event.setRadius(def.power());
                event.setFire(def.fire());
                return;
            }
        }
    }

    private void destroyArenaBlocks(Location center, float radius) {
        int r = (int) Math.ceil(radius);
        int cx = center.getBlockX();
        int cy = center.getBlockY();
        int cz = center.getBlockZ();
        double r2 = radius * radius;
        for (int dx = -r; dx <= r; dx++) {
            for (int dy = -r; dy <= r; dy++) {
                for (int dz = -r; dz <= r; dz++) {
                    if (dx * dx + dy * dy + dz * dz > r2) continue;
                    int x = cx + dx, y = cy + dy, z = cz + dz;
                    if (!config.isInsideInner(x, y, z)) continue;
                    Block b = config.world.getBlockAt(x, y, z);
                    Material m = b.getType();
                    if (m == Material.AIR || m == config.wallMaterial) continue;
                    b.setType(Material.AIR, false);
                }
            }
        }
    }

    private void spawnCreeperHorde(Location loc, Component name) {
        int count = config.creeperCount;
        int walkTicks = config.creeperWalkTicks;
        int spawned = 0;
        for (int i = 0; i < count; i++) {
            double ox = (rnd.nextDouble() - 0.5) * 4;
            double oz = (rnd.nextDouble() - 0.5) * 4;
            int maxY = Math.max(loc.getBlockY(), config.minY + 2);
            Location spawn = new Location(
                    loc.getWorld(),
                    loc.getX() + ox,
                    maxY + 0.2,
                    loc.getZ() + oz,
                    rnd.nextFloat() * 360f, 0f
            );
            try {
                Creeper creeper = loc.getWorld().spawn(
                        spawn, Creeper.class,
                        CreatureSpawnEvent.SpawnReason.CUSTOM,
                        cr -> {
                            if (name != null) {
                                cr.customName(name);
                                cr.setCustomNameVisible(true);
                            }
                            cr.setRemoveWhenFarAway(false);
                            cr.setPersistent(true);
                            cr.addScoreboardTag("box_creeper_mob");
                        }
                );
                if (creeper == null || !creeper.isValid()) {
                    plugin.getLogger().warning("Creeper spawn null/invalid at " + spawn);
                    continue;
                }
                spawned++;
                int fuseDelay = walkTicks + rnd.nextInt(30);
                new BukkitRunnable() {
                    @Override
                    public void run() {
                        if (creeper.isValid() && !creeper.isDead()) {
                            creeper.ignite();
                        }
                    }
                }.runTaskLater(plugin, fuseDelay);
            } catch (Exception ex) {
                plugin.getLogger().warning("Creeper spawn hatasi: " + ex.getMessage());
            }
        }
        plugin.getLogger().info("[creeper] " + spawned + "/" + count + " creeper spawn edildi @ " + loc.getBlockX() + "," + loc.getBlockY() + "," + loc.getBlockZ());
    }
}
