package com.kenfroz.tiktokbox;

import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;
import net.kyori.adventure.title.Title;
import org.bukkit.Bukkit;
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.World;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.entity.Zombie;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.CreatureSpawnEvent;
import org.bukkit.event.entity.PlayerDeathEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.inventory.ItemStack;
import org.bukkit.plugin.java.JavaPlugin;
import org.bukkit.scheduler.BukkitRunnable;

import java.time.Duration;
import java.util.ArrayList;
import java.util.Collection;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

public class PenaltyManager implements Listener {
    private final JavaPlugin plugin;
    private final ArenaConfig config;
    private final Map<UUID, PenaltyState> active = new HashMap<>();

    public PenaltyManager(JavaPlugin plugin, ArenaConfig config) {
        this.plugin = plugin;
        this.config = config;
        buildPrison();
        buildGauntlet();
    }

    private static class PenaltyState {
        final String kind;
        final Location origin;
        final GameMode mode;
        final ItemStack[] inv;
        final ItemStack[] armor;
        final double health;
        final int food;
        final List<UUID> mobs = new ArrayList<>();
        BukkitRunnable timer;

        PenaltyState(Player p, String kind) {
            this.kind = kind;
            this.origin = p.getLocation().clone();
            this.mode = p.getGameMode();
            this.inv = p.getInventory().getContents().clone();
            this.armor = p.getInventory().getArmorContents().clone();
            this.health = p.getHealth();
            this.food = p.getFoodLevel();
        }
    }

    public boolean isActive(Player p) {
        return active.containsKey(p.getUniqueId());
    }

    public boolean startPrison(Player p) {
        if (isActive(p)) return false;
        PenaltyState st = new PenaltyState(p, "prison");
        active.put(p.getUniqueId(), st);
        Location cell = prisonLoc();
        p.setGameMode(GameMode.ADVENTURE);
        p.teleport(cell);
        announceTitle(p, "HAPSE ATILDIN", "10 saniye bekle", NamedTextColor.DARK_RED);
        broadcast(p.getName() + " hapse atildi (10sn)", NamedTextColor.LIGHT_PURPLE);
        st.timer = new BukkitRunnable() {
            int leftTicks = config.penaltyPrisonTicks;
            @Override
            public void run() {
                if (!p.isOnline() || !active.containsKey(p.getUniqueId())) { cancel(); return; }
                int s = (leftTicks + 19) / 20;
                p.sendActionBar(Component.text("HAPISTE: " + s + "s", NamedTextColor.RED));
                leftTicks -= 10;
                if (leftTicks <= 0) {
                    endPenalty(p, true, "Cikis serbest");
                    cancel();
                }
            }
        };
        st.timer.runTaskTimer(plugin, 0L, 10L);
        return true;
    }

    public boolean startGauntlet(Player p) {
        if (isActive(p)) return false;
        PenaltyState st = new PenaltyState(p, "gauntlet");
        active.put(p.getUniqueId(), st);
        Location arena = gauntletLoc();
        p.getInventory().clear();
        p.getInventory().setArmorContents(new ItemStack[]{
                new ItemStack(Material.IRON_BOOTS),
                new ItemStack(Material.IRON_LEGGINGS),
                new ItemStack(Material.IRON_CHESTPLATE),
                new ItemStack(Material.IRON_HELMET)
        });
        p.getInventory().addItem(new ItemStack(Material.IRON_SWORD));
        p.getInventory().addItem(new ItemStack(Material.COOKED_BEEF, 8));
        p.setGameMode(GameMode.SURVIVAL);
        p.setHealth(20.0);
        p.setFoodLevel(20);
        p.setFireTicks(0);
        p.teleport(arena);
        announceTitle(p, "HAYATTA KAL", "30 saniye - canavarlari yen!", NamedTextColor.DARK_RED);
        broadcast(p.getName() + " canavarlara yem edildi (30sn)", NamedTextColor.LIGHT_PURPLE);
        spawnGauntletMobs(st, arena);
        st.timer = new BukkitRunnable() {
            int leftTicks = config.penaltyGauntletTicks;
            @Override
            public void run() {
                if (!p.isOnline() || !active.containsKey(p.getUniqueId())) { cancel(); return; }
                int s = (leftTicks + 19) / 20;
                int alive = 0;
                for (UUID mid : st.mobs) {
                    Entity e = Bukkit.getEntity(mid);
                    if (e != null && e.isValid() && !e.isDead()) alive++;
                }
                p.sendActionBar(Component.text("KAL: " + s + "s | Canavar: " + alive,
                        alive == 0 ? NamedTextColor.GREEN : NamedTextColor.GOLD));
                leftTicks -= 10;
                if (leftTicks <= 0) {
                    announceTitle(p, "HAYATTA KALDIN!", "Zafer!", NamedTextColor.GOLD);
                    endPenalty(p, true, "Hayatta kaldin");
                    cancel();
                }
            }
        };
        st.timer.runTaskTimer(plugin, 0L, 10L);
        return true;
    }

    private void spawnGauntletMobs(PenaltyState st, Location center) {
        int count = config.penaltyGauntletMobCount;
        World w = center.getWorld();
        double radius = Math.max(3, config.penaltyGauntletSize / 2.0 - 2);
        for (int i = 0; i < count; i++) {
            double ox = (Math.random() - 0.5) * 2 * radius;
            double oz = (Math.random() - 0.5) * 2 * radius;
            Location spawn = center.clone().add(ox, 0, oz);
            try {
                Zombie z = w.spawn(spawn, Zombie.class,
                        CreatureSpawnEvent.SpawnReason.CUSTOM,
                        zb -> {
                            zb.setPersistent(true);
                            zb.setRemoveWhenFarAway(false);
                            zb.setCanPickupItems(false);
                            zb.addScoreboardTag("box_penalty_mob");
                        });
                if (z != null) st.mobs.add(z.getUniqueId());
            } catch (Exception e) {
                plugin.getLogger().warning("Gauntlet mob spawn hatasi: " + e.getMessage());
            }
        }
    }

    public void endPenalty(Player p, boolean teleportBack, String reason) {
        PenaltyState st = active.remove(p.getUniqueId());
        if (st == null) return;
        if (st.timer != null) {
            try { st.timer.cancel(); } catch (Exception ignore) {}
        }
        for (UUID mid : st.mobs) {
            Entity e = Bukkit.getEntity(mid);
            if (e != null) e.remove();
        }
        // Stray penalty-mob temizligi
        for (World w : Bukkit.getWorlds()) {
            for (Entity e : w.getEntities()) {
                if (e.getScoreboardTags().contains("box_penalty_mob")) e.remove();
            }
        }
        if (!p.isOnline()) return;
        p.setGameMode(st.mode);
        p.getInventory().setContents(st.inv);
        p.getInventory().setArmorContents(st.armor);
        p.setHealth(20.0);
        p.setFoodLevel(20);
        p.setFireTicks(0);
        if (teleportBack) p.teleport(st.origin);
        if (reason != null && !reason.isEmpty()) {
            broadcast(p.getName() + ": " + reason, NamedTextColor.AQUA);
        }
    }

    @EventHandler
    public void onDeath(PlayerDeathEvent event) {
        Player p = event.getEntity();
        PenaltyState st = active.get(p.getUniqueId());
        if (st == null) return;
        if ("gauntlet".equals(st.kind)) {
            event.setCancelled(true);
            event.getDrops().clear();
            event.setDeathMessage(null);
            announceTitle(p, "OLDURULDUN", "Kurtariliyorsun...", NamedTextColor.RED);
            Bukkit.getScheduler().runTask(plugin, () -> {
                p.setHealth(20.0);
                endPenalty(p, true, "Canavarlar kazandi");
            });
        }
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent event) {
        PenaltyState st = active.remove(event.getPlayer().getUniqueId());
        if (st == null) return;
        if (st.timer != null) try { st.timer.cancel(); } catch (Exception ignore) {}
        for (UUID mid : st.mobs) {
            Entity e = Bukkit.getEntity(mid);
            if (e != null) e.remove();
        }
    }

    public void endAll() {
        List<UUID> ids = new ArrayList<>(active.keySet());
        for (UUID id : ids) {
            Player p = Bukkit.getPlayer(id);
            if (p != null) endPenalty(p, true, null);
        }
    }

    private void announceTitle(Player p, String main, String sub, NamedTextColor color) {
        Title title = Title.title(
                Component.text(main, color),
                Component.text(sub, NamedTextColor.YELLOW),
                Title.Times.times(Duration.ofMillis(200), Duration.ofSeconds(2), Duration.ofMillis(500))
        );
        p.showTitle(title);
    }

    private void broadcast(String msg, NamedTextColor color) {
        Bukkit.broadcast(Component.text("[Ceza] " + msg, color));
    }

    private Location prisonLoc() {
        return new Location(config.world,
                config.penaltyPrisonX + 0.5,
                config.penaltyPrisonY,
                config.penaltyPrisonZ + 0.5,
                0f, 0f);
    }

    private Location gauntletLoc() {
        return new Location(config.world,
                config.penaltyGauntletX + 0.5,
                config.penaltyGauntletY,
                config.penaltyGauntletZ + 0.5,
                0f, 0f);
    }

    /** Hucre: 3x3 tabanda 3 blok yuksek bedrock kutu, ici bos. */
    private void buildPrison() {
        int cx = config.penaltyPrisonX;
        int cy = config.penaltyPrisonY;
        int cz = config.penaltyPrisonZ;
        for (int dx = -1; dx <= 1; dx++) {
            for (int dz = -1; dz <= 1; dz++) {
                for (int dy = -1; dy <= 3; dy++) {
                    Material m = Material.BEDROCK;
                    if (dx != -1 && dx != 1 && dz != -1 && dz != 1 && dy >= 0 && dy <= 2) m = Material.AIR;
                    config.world.getBlockAt(cx + dx, cy + dy, cz + dz).setType(m, false);
                }
            }
        }
        // isik
        config.world.getBlockAt(cx, cy + 2, cz).setType(Material.GLOWSTONE, false);
    }

    /** Gauntlet: size x size bedrock duvarli tas zemin, 6 blok yukseklik, tavan acik. */
    private void buildGauntlet() {
        int cx = config.penaltyGauntletX;
        int cy = config.penaltyGauntletY;
        int cz = config.penaltyGauntletZ;
        int half = Math.max(4, config.penaltyGauntletSize / 2);
        int h = 6;
        // zemin
        for (int x = -half; x <= half; x++)
            for (int z = -half; z <= half; z++)
                config.world.getBlockAt(cx + x, cy - 1, cz + z).setType(Material.STONE_BRICKS, false);
        // ic bosaltma
        for (int x = -half + 1; x <= half - 1; x++)
            for (int y = 0; y < h; y++)
                for (int z = -half + 1; z <= half - 1; z++)
                    config.world.getBlockAt(cx + x, cy + y, cz + z).setType(Material.AIR, false);
        // duvarlar
        for (int x = -half; x <= half; x++)
            for (int y = 0; y < h; y++) {
                config.world.getBlockAt(cx + x, cy + y, cz - half).setType(Material.BEDROCK, false);
                config.world.getBlockAt(cx + x, cy + y, cz + half).setType(Material.BEDROCK, false);
            }
        for (int z = -half + 1; z <= half - 1; z++)
            for (int y = 0; y < h; y++) {
                config.world.getBlockAt(cx - half, cy + y, cz + z).setType(Material.BEDROCK, false);
                config.world.getBlockAt(cx + half, cy + y, cz + z).setType(Material.BEDROCK, false);
            }
    }
}
