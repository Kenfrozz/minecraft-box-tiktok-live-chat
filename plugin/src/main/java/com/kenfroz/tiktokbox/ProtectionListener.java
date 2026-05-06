package com.kenfroz.tiktokbox;

import org.bukkit.Bukkit;
import org.bukkit.Material;
import org.bukkit.attribute.Attribute;
import org.bukkit.attribute.AttributeInstance;
import org.bukkit.block.Block;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.block.BlockBreakEvent;
import org.bukkit.event.block.BlockPlaceEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.plugin.java.JavaPlugin;
import org.bukkit.potion.PotionEffect;
import org.bukkit.potion.PotionEffectType;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;

public class ProtectionListener implements Listener {
    private final JavaPlugin plugin;
    private final ArenaConfig config;

    public ProtectionListener(JavaPlugin plugin, ArenaConfig config) {
        this.plugin = plugin;
        this.config = config;
    }

    @EventHandler
    public void onBreak(BlockBreakEvent event) {
        Block b = event.getBlock();
        if (b.getType() == config.wallMaterial) {
            event.setCancelled(true);
            event.getPlayer().sendActionBar(
                Component.text("Ana kaya kirilamaz", NamedTextColor.RED)
            );
        }
    }

    @EventHandler(priority = EventPriority.HIGH)
    public void onPlaceBedrock(BlockPlaceEvent event) {
        if (event.getBlockPlaced().getType() == config.wallMaterial) {
            event.setCancelled(true);
            event.getPlayer().sendActionBar(
                Component.text("Ana kaya yerlestirilemez", NamedTextColor.RED)
            );
        }
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onPlace(BlockPlaceEvent event) {
        Block b = event.getBlockPlaced();
        int x = b.getX(), y = b.getY(), z = b.getZ();
        if (!config.isInsideInner(x, y, z)) return;
        TierDefinition tier = config.tierForY(y);
        if (tier == null) return;
        Material target = tier.block();
        int radius = Math.max(0, config.fastPlaceRadius);
        Bukkit.getScheduler().runTask(plugin, () -> {
            if (config.autoConvertPlaced && b.getType() != target) b.setType(target, false);
            if (radius <= 0) return;
            for (int dx = -radius; dx <= radius; dx++) {
                for (int dz = -radius; dz <= radius; dz++) {
                    if (dx == 0 && dz == 0) continue;
                    int nx = x + dx, nz = z + dz;
                    if (!config.isInsideInner(nx, y, nz)) continue;
                    Block nb = config.world.getBlockAt(nx, y, nz);
                    if (nb.getType() == Material.AIR) nb.setType(target, false);
                }
            }
        });
    }

    @EventHandler
    public void onJoin(PlayerJoinEvent event) {
        Player p = event.getPlayer();
        applyAttributes(p);
    }

    public void applyAttributes(Player p) {
        setBase(p, Attribute.BLOCK_INTERACTION_RANGE, config.blockReach);
        setBase(p, Attribute.ENTITY_INTERACTION_RANGE, config.entityReach);
        setBase(p, Attribute.BLOCK_BREAK_SPEED, config.blockBreakSpeed);
        setBase(p, Attribute.MINING_EFFICIENCY, config.miningEfficiency);
        p.addPotionEffect(new PotionEffect(PotionEffectType.HASTE,
                PotionEffect.INFINITE_DURATION, config.hasteAmplifier,
                true, false, false));
        p.addPotionEffect(new PotionEffect(PotionEffectType.NIGHT_VISION,
                PotionEffect.INFINITE_DURATION, 0,
                true, false, false));
    }

    private void setBase(Player p, Attribute attr, double value) {
        AttributeInstance inst = p.getAttribute(attr);
        if (inst != null) inst.setBaseValue(value);
    }
}
