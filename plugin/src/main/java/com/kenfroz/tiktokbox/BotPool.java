package com.kenfroz.tiktokbox;

import org.bukkit.Bukkit;
import org.bukkit.GameMode;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.EntityDamageEvent;
import org.bukkit.event.world.ChunkLoadEvent;
import org.bukkit.plugin.java.JavaPlugin;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * Birden fazla yardimci bot'u (HelperBot) yonetir.
 * - Hediye geldiginde yeni bot spawn olur (hediye eden kisinin adi ile)
 * - Max bot limiti asiliyorsa en eski bot silinir (FIFO)
 * - stopAll tum botlari temizler
 */
public class BotPool implements Listener {
    private final JavaPlugin plugin;
    private final ArenaConfig config;
    private final List<HelperBot> bots = new ArrayList<>();
    private final Map<UUID, GameMode> watchers = new HashMap<>();
    private static final int MAX_BOTS = 20;

    public BotPool(JavaPlugin plugin, ArenaConfig config) {
        this.plugin = plugin;
        this.config = config;
    }

    public int size() { return bots.size(); }
    public boolean isAnyRunning() {
        pruneDead();
        return !bots.isEmpty();
    }

    public List<HelperBot> all() {
        pruneDead();
        return new ArrayList<>(bots);
    }

    private void pruneDead() {
        Iterator<HelperBot> it = bots.iterator();
        while (it.hasNext()) {
            HelperBot b = it.next();
            if (!b.isRunning()) it.remove();
        }
    }

    /** Manuel start: yeni bot spawn et. */
    public HelperBot spawn(int bps, String type, String name) {
        pruneDead();
        if (bots.size() >= MAX_BOTS) {
            // En eski botu sil
            HelperBot old = bots.remove(0);
            old.stop();
        }
        HelperBot b = new HelperBot(plugin, config);
        boolean ok = b.start(
                bps > 0 ? bps : config.botDefaultBps,
                (type == null || type.isBlank()) ? config.botDefaultType : type,
                (name == null || name.isBlank()) ? config.botDefaultName : name);
        if (!ok) return null;
        bots.add(b);
        return b;
    }

    /** Hediye geldiginde cagrilir: her hediye yeni bir bot spawn eder. */
    public HelperBot summonFromGift(String donorName) {
        return spawn(config.botDefaultBps, config.botDefaultType, donorName);
    }

    public int stopAll() {
        int n = bots.size();
        for (HelperBot b : bots) {
            try { b.stop(); } catch (Exception ignore) {}
        }
        bots.clear();
        // Guvenlik: tag'li tum entity'leri sil
        for (Entity e : config.world.getEntities()) {
            if (e.getScoreboardTags().contains("box_helper_bot")) e.remove();
        }
        return n;
    }

    public HelperBot latest() {
        pruneDead();
        return bots.isEmpty() ? null : bots.get(bots.size() - 1);
    }

    public boolean watch(Player p) {
        HelperBot b = latest();
        if (b == null) return false;
        if (!watchers.containsKey(p.getUniqueId())) {
            watchers.put(p.getUniqueId(), p.getGameMode());
        }
        p.setGameMode(GameMode.SPECTATOR);
        HelperBot target = b;
        Bukkit.getScheduler().runTaskLater(plugin, () -> {
            if (p.isOnline() && target.isRunning()) {
                p.setSpectatorTarget(target.entity());
            }
        }, 2L);
        return true;
    }

    public boolean unwatch(Player p) {
        GameMode original = watchers.remove(p.getUniqueId());
        if (original == null) return false;
        try { p.setSpectatorTarget(null); } catch (Exception ignore) {}
        p.setGameMode(original);
        return true;
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onDamage(EntityDamageEvent event) {
        if (event.getEntity().getScoreboardTags().contains("box_helper_bot")) {
            event.setCancelled(true);
        }
    }

    /**
     * Chunk yuklendiginde o chunkta takip edilmeyen bir helper bot varsa (onceki
     * oturumdan kalma AFK bot), temizle. 1 tick gecikme ile entity state stabillesir.
     */
    @EventHandler
    public void onChunkLoad(ChunkLoadEvent event) {
        plugin.getServer().getScheduler().runTaskLater(plugin, () -> {
            for (Entity e : event.getChunk().getEntities()) {
                if (!e.getScoreboardTags().contains("box_helper_bot")) continue;
                boolean tracked = false;
                for (HelperBot b : bots) {
                    UUID uid = b.botUuid();
                    if (uid != null && uid.equals(e.getUniqueId())) {
                        tracked = true;
                        break;
                    }
                }
                if (!tracked) {
                    plugin.getLogger().info("Orphan bot temizlendi: " + e.getType() + " @ chunk " + event.getChunk().getX() + "," + event.getChunk().getZ());
                    e.remove();
                }
            }
        }, 1L);
    }
}
