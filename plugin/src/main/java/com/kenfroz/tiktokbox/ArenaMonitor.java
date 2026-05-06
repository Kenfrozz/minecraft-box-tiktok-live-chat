package com.kenfroz.tiktokbox;

import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;
import net.kyori.adventure.title.Title;
import net.kyori.adventure.sound.Sound;
import org.bukkit.Bukkit;
import org.bukkit.Material;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.scheduler.BukkitRunnable;
import org.bukkit.plugin.java.JavaPlugin;

import java.time.Duration;

public class ArenaMonitor extends BukkitRunnable {
    private final JavaPlugin plugin;
    private final ArenaConfig config;
    private final StatsManager stats;
    private final HudManager hud;

    private int filled;
    private int total;
    private int[] tierFilled;
    private int[] tierTotal;

    private boolean countdownActive = false;
    private int countdownTicksLeft = 0;
    private boolean gameWon = false;

    public ArenaMonitor(JavaPlugin plugin, ArenaConfig config, StatsManager stats, HudManager hud) {
        this.plugin = plugin;
        this.config = config;
        this.stats = stats;
        this.hud = hud;
        this.tierFilled = new int[config.tiers.size()];
        this.tierTotal = new int[config.tiers.size()];
        for (int i = 0; i < config.tiers.size(); i++) {
            var t = config.tiers.get(i);
            tierTotal[i] = config.sizeX * config.sizeZ * (t.yMax() - t.yMin() + 1);
            total += tierTotal[i];
        }
    }

    @Override
    public void run() {
        if (gameWon) return;
        scan();
        hud.update(filled, total, countdownActive, getCountdownSecondsLeft());
        checkCountdown();
    }

    private void scan() {
        World world = config.world;
        filled = 0;
        for (int i = 0; i < tierFilled.length; i++) tierFilled[i] = 0;
        for (int i = 0; i < config.tiers.size(); i++) {
            TierDefinition t = config.tiers.get(i);
            Material target = t.block();
            for (int x = config.minX; x <= config.maxX; x++) {
                for (int z = config.minZ; z <= config.maxZ; z++) {
                    for (int y = t.yMin(); y <= t.yMax(); y++) {
                        Block b = world.getBlockAt(x, y, z);
                        if (b.getType() == target) {
                            tierFilled[i]++;
                            filled++;
                        }
                    }
                }
            }
        }
    }

    private void checkCountdown() {
        boolean full = filled >= total;
        if (full) {
            if (!countdownActive) startCountdown();
        } else {
            if (countdownActive) cancelCountdown();
        }
    }

    private void startCountdown() {
        countdownActive = true;
        countdownTicksLeft = config.winSeconds * 20;
        Bukkit.broadcast(Component.text("Arena doldu! " + config.winSeconds
                + " saniye geri sayim basladi", NamedTextColor.GOLD));
        new BukkitRunnable() {
            int lastSecond = -1;
            @Override
            public void run() {
                if (!countdownActive || gameWon) { cancel(); return; }
                int secondsLeft = (countdownTicksLeft + 19) / 20;
                if (secondsLeft != lastSecond) {
                    lastSecond = secondsLeft;
                    if (secondsLeft > 0) {
                        Title title = Title.title(
                            Component.text(String.valueOf(secondsLeft), NamedTextColor.GREEN),
                            Component.text("ZAFERE", NamedTextColor.YELLOW),
                            Title.Times.times(Duration.ZERO, Duration.ofMillis(1100), Duration.ofMillis(200))
                        );
                        Bukkit.getOnlinePlayers().forEach(p -> {
                            p.showTitle(title);
                            p.playSound(Sound.sound(org.bukkit.Sound.BLOCK_NOTE_BLOCK_PLING.getKey(),
                                    Sound.Source.MASTER, 1f, 1.5f));
                        });
                    }
                }
                countdownTicksLeft--;
                if (countdownTicksLeft <= 0) {
                    winGame();
                    cancel();
                }
            }
        }.runTaskTimer(plugin, 0L, 1L);
    }

    private void cancelCountdown() {
        if (!countdownActive) return;
        countdownActive = false;
        Title title = Title.title(
            Component.text("SABOTAJ!", NamedTextColor.RED),
            Component.text("Bir blok gitti", NamedTextColor.YELLOW),
            Title.Times.times(Duration.ZERO, Duration.ofSeconds(1), Duration.ofMillis(300))
        );
        Bukkit.getOnlinePlayers().forEach(p -> {
            p.showTitle(title);
            p.playSound(Sound.sound(org.bukkit.Sound.ENTITY_WITHER_HURT.getKey(),
                    Sound.Source.MASTER, 1f, 0.8f));
        });
    }

    private void winGame() {
        gameWon = true;
        countdownActive = false;
        stats.incrementWins();
        Title title = Title.title(
            Component.text("KAZANDIN!", NamedTextColor.GOLD),
            Component.text("Toplam zafer: " + stats.getWins(), NamedTextColor.GREEN),
            Title.Times.times(Duration.ofMillis(200), Duration.ofSeconds(3), Duration.ofSeconds(1))
        );
        Bukkit.getOnlinePlayers().forEach(p -> {
            p.showTitle(title);
            p.playSound(Sound.sound(org.bukkit.Sound.UI_TOAST_CHALLENGE_COMPLETE.getKey(),
                    Sound.Source.MASTER, 1f, 1f));
        });
        Bukkit.broadcast(Component.text("★ Zafer #" + stats.getWins() + " kazanildi!", NamedTextColor.GOLD));

        // Kisa gecikme sonra arenayi bosalt + state sifirla
        Bukkit.getScheduler().runTaskLater(plugin, () -> {
            clearArena();
            scan();
            gameWon = false;
            hud.update(filled, total, false, 0);
            Bukkit.broadcast(Component.text("Arena temizlendi - yeni tur basladi!", NamedTextColor.AQUA));
        }, 100L); // 5 saniye
    }

    public void clearArena() {
        for (int x = config.minX; x <= config.maxX; x++)
            for (int y = config.minY; y <= config.maxY; y++)
                for (int z = config.minZ; z <= config.maxZ; z++)
                    config.world.getBlockAt(x, y, z).setType(Material.AIR, false);
    }

    public int getFilled() { return filled; }
    public int getTotal() { return total; }
    public boolean isWon() { return gameWon; }
    public boolean isCountdownActive() { return countdownActive; }
    public int getCountdownSecondsLeft() { return (countdownTicksLeft + 19) / 20; }

    public void reset() {
        gameWon = false;
        countdownActive = false;
        countdownTicksLeft = 0;
    }
}
