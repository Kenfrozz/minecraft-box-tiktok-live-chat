package com.kenfroz.tiktokbox;

import org.bukkit.Bukkit;
import org.bukkit.Difficulty;
import org.bukkit.GameRule;
import org.bukkit.World;
import org.bukkit.plugin.java.JavaPlugin;

public class TikTokBoxPlugin extends JavaPlugin {
    private ArenaConfig arenaConfig;
    private ArenaMonitor monitor;
    private ProtectionListener protection;
    private StatsManager stats;
    private HudManager hud;
    private PenaltyManager penalty;
    private BotPool botPool;

    @Override
    public void onEnable() {
        saveDefaultConfig();
        try {
            this.arenaConfig = new ArenaConfig(getConfig());
        } catch (Exception e) {
            getLogger().severe("Config yukleme hatasi: " + e.getMessage());
            setEnabled(false);
            return;
        }

        this.stats = new StatsManager(this);
        this.hud = new HudManager(stats);

        this.protection = new ProtectionListener(this, arenaConfig);
        Bukkit.getPluginManager().registerEvents(protection, this);
        Bukkit.getPluginManager().registerEvents(new TNTManager(this, arenaConfig), this);
        Bukkit.getPluginManager().registerEvents(new DropBlocker(arenaConfig), this);
        Bukkit.getPluginManager().registerEvents(new HudJoinListener(hud), this);

        this.monitor = new ArenaMonitor(this, arenaConfig, stats, hud);
        monitor.runTaskTimer(this, 20L, arenaConfig.scanIntervalTicks);

        this.penalty = new PenaltyManager(this, arenaConfig);
        Bukkit.getPluginManager().registerEvents(penalty, this);

        this.botPool = new BotPool(this, arenaConfig);
        Bukkit.getPluginManager().registerEvents(botPool, this);

        getCommand("arena").setExecutor(new ArenaCommand(this, arenaConfig, monitor, stats, hud, penalty, botPool));

        if (arenaConfig.botAutoStart) {
            Bukkit.getScheduler().runTaskLater(this, () -> {
                botPool.spawn(arenaConfig.botDefaultBps, arenaConfig.botDefaultType, arenaConfig.botDefaultName);
                getLogger().info("Varsayilan bot spawn edildi: " + arenaConfig.botDefaultType + " '" + arenaConfig.botDefaultName + "'");
            }, 40L);
        }

        applyWorldRules(arenaConfig.world);
        cleanupOrphanEntities(arenaConfig.world);

        Bukkit.getOnlinePlayers().forEach(p -> {
            protection.applyAttributes(p);
            hud.showTo(p);
        });

        getLogger().info("TikTokBox aktif. Arena: "
                + arenaConfig.sizeX + "x" + arenaConfig.sizeY + "x" + arenaConfig.sizeZ
                + " = " + arenaConfig.totalBlocks() + " blok. Wins: " + stats.getWins());
    }

    private void cleanupOrphanEntities(World w) {
        int removed = 0;
        for (var e : w.getEntities()) {
            var tags = e.getScoreboardTags();
            if (tags.contains("box_helper_bot") || tags.contains("box_penalty_mob") || tags.contains("box_creeper_mob")) {
                e.remove();
                removed++;
            }
        }
        if (removed > 0) getLogger().info("Temizlenen artik entity: " + removed);
    }

    private void applyWorldRules(World w) {
        w.setGameRule(GameRule.DO_MOB_SPAWNING, true);
        w.setGameRule(GameRule.DO_INSOMNIA, false);
        w.setGameRule(GameRule.DO_PATROL_SPAWNING, false);
        w.setGameRule(GameRule.DO_TRADER_SPAWNING, false);
        w.setGameRule(GameRule.DISABLE_RAIDS, true);
        w.setGameRule(GameRule.DO_DAYLIGHT_CYCLE, false);
        w.setGameRule(GameRule.DO_WEATHER_CYCLE, false);
        w.setGameRule(GameRule.DO_FIRE_TICK, false);
        w.setGameRule(GameRule.DO_TILE_DROPS, false);
        w.setGameRule(GameRule.MOB_GRIEFING, false);
        w.setGameRule(GameRule.RANDOM_TICK_SPEED, 0);
        w.setGameRule(GameRule.DO_ENTITY_DROPS, false);
        w.setGameRule(GameRule.ANNOUNCE_ADVANCEMENTS, false);
        w.setTime(6000);
        w.setStorm(false);
        w.setThundering(false);
        if (w.getDifficulty() == Difficulty.PEACEFUL) {
            w.setDifficulty(Difficulty.EASY);
        }
    }

    @Override
    public void onDisable() {
        if (botPool != null) botPool.stopAll();
        if (penalty != null) penalty.endAll();
        if (monitor != null) monitor.cancel();
        if (hud != null) hud.hideAll();
        if (stats != null) stats.save();
        getLogger().info("TikTokBox kapatildi.");
    }

    public ArenaConfig getArenaConfig() { return arenaConfig; }
    public ArenaMonitor getMonitor() { return monitor; }
    public StatsManager getStats() { return stats; }
    public HudManager getHud() { return hud; }
}
