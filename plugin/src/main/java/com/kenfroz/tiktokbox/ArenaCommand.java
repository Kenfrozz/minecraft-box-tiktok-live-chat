package com.kenfroz.tiktokbox;

import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.block.Block;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.entity.TNTPrimed;
import org.bukkit.plugin.java.JavaPlugin;

import java.util.Locale;
import java.util.Random;

public class ArenaCommand implements CommandExecutor {
    private final JavaPlugin plugin;
    private final ArenaConfig config;
    private final ArenaMonitor monitor;
    private final StatsManager stats;
    private final HudManager hud;
    private final PenaltyManager penalty;
    private final BotPool botPool;
    private final Random random = new Random();

    public ArenaCommand(JavaPlugin plugin, ArenaConfig config, ArenaMonitor monitor,
                        StatsManager stats, HudManager hud, PenaltyManager penalty,
                        BotPool botPool) {
        this.plugin = plugin;
        this.config = config;
        this.monitor = monitor;
        this.stats = stats;
        this.hud = hud;
        this.penalty = penalty;
        this.botPool = botPool;
    }

    private void reply(CommandSender s, String text, NamedTextColor c) {
        s.sendMessage(Component.text(text, c));
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (args.length == 0) {
            reply(sender, "/arena <status|clear|fill|win|tnt <tier>|inv|tp|speed|gift|wins|hud|penalty <prison|gauntlet|end>>",
                    NamedTextColor.YELLOW);
            return true;
        }
        String sub = args[0].toLowerCase(Locale.ROOT);
        switch (sub) {
            case "status" -> {
                int pct = monitor.getTotal() == 0 ? 0 : monitor.getFilled() * 100 / monitor.getTotal();
                reply(sender, "Arena: " + monitor.getFilled() + "/" + monitor.getTotal() + " (" + pct + "%)"
                        + "  Wins: " + stats.getWins()
                        + (monitor.isCountdownActive() ? " CD: " + monitor.getCountdownSecondsLeft() + "s" : "")
                        + (monitor.isWon() ? " KAZANILDI" : ""), NamedTextColor.AQUA);
            }
            case "clear", "reset" -> {
                int cleared = clearArena();
                monitor.reset();
                reply(sender, "Arena temizlendi: " + cleared + " blok", NamedTextColor.GREEN);
            }
            case "fill" -> {
                if (args.length < 2) {
                    int filled = fillArena(100);
                    reply(sender, "Fill %100: " + filled + " blok", NamedTextColor.GREEN);
                } else {
                    String arg = args[1].toLowerCase(Locale.ROOT);
                    if (arg.matches("\\d+")) {
                        int pct = Math.max(0, Math.min(100, Integer.parseInt(arg)));
                        clearArena(); monitor.reset();
                        int filled = fillArena(pct);
                        reply(sender, "Fill %" + pct + ": " + filled + " blok", NamedTextColor.GREEN);
                    } else {
                        TierDefinition t = findTier(arg);
                        if (t == null) { reply(sender, "Bilinmeyen tier: " + arg, NamedTextColor.RED); return true; }
                        int filled = fillTier(t);
                        reply(sender, "Tier '" + t.name() + "' dolduruldu: " + filled + " blok", NamedTextColor.GREEN);
                    }
                }
            }
            case "win" -> {
                fillArena(100);
                reply(sender, "Arena dolduruldu - countdown baslayacak", NamedTextColor.GOLD);
            }
            case "tnt" -> {
                String tier = args.length >= 2 ? args[1].toLowerCase(Locale.ROOT) : "normal";
                spawnTnt(tier);
                reply(sender, "TNT tetiklendi: " + tier, NamedTextColor.RED);
            }
            case "cleartnt" -> {
                int removed = 0;
                for (Entity e : config.world.getEntities()) if (e instanceof TNTPrimed) { e.remove(); removed++; }
                reply(sender, "Aktif TNT silindi: " + removed, NamedTextColor.YELLOW);
            }
            case "inv" -> {
                if (!(sender instanceof Player p)) { reply(sender, "Sadece oyuncu", NamedTextColor.RED); return true; }
                p.getInventory().clear();
                p.getInventory().addItem(new org.bukkit.inventory.ItemStack(Material.IRON_BLOCK, 64));
                p.getInventory().addItem(new org.bukkit.inventory.ItemStack(Material.GOLD_BLOCK, 64));
                p.getInventory().addItem(new org.bukkit.inventory.ItemStack(Material.DIAMOND_BLOCK, 64));
                p.getInventory().addItem(new org.bukkit.inventory.ItemStack(Material.STONE_BRICKS, 64));
                p.getInventory().addItem(new org.bukkit.inventory.ItemStack(Material.TNT, 64));
                reply(sender, "Envanter yenilendi", NamedTextColor.GREEN);
            }
            case "tp" -> {
                if (!(sender instanceof Player p)) { reply(sender, "Sadece oyuncu", NamedTextColor.RED); return true; }
                int cx = (config.minX + config.maxX) / 2;
                int cz = config.minZ - 8;
                int cy = (config.minY + config.maxY) / 2;
                p.teleport(new Location(config.world, cx + 0.5, cy, cz + 0.5, 0f, 15f));
                reply(sender, "Arena yanina TP", NamedTextColor.GREEN);
            }
            case "speed" -> {
                if (!(sender instanceof Player p)) { reply(sender, "Sadece oyuncu", NamedTextColor.RED); return true; }
                double v = args.length >= 2 ? Double.parseDouble(args[1]) : 10.0;
                var a1 = p.getAttribute(org.bukkit.attribute.Attribute.BLOCK_BREAK_SPEED);
                var a2 = p.getAttribute(org.bukkit.attribute.Attribute.MINING_EFFICIENCY);
                var a3 = p.getAttribute(org.bukkit.attribute.Attribute.ATTACK_SPEED);
                if (a1 != null) a1.setBaseValue(v);
                if (a2 != null) a2.setBaseValue(v);
                if (a3 != null) a3.setBaseValue(v);
                reply(sender, "Hiz attributeleri " + v + "x", NamedTextColor.GREEN);
            }
            case "gift" -> {
                if (args.length < 3) { reply(sender, "Kullanim: /arena gift <user> <coins>", NamedTextColor.RED); return true; }
                String user = args[1];
                long coins;
                try { coins = Long.parseLong(args[2]); }
                catch (NumberFormatException e) { reply(sender, "Gecersiz coin", NamedTextColor.RED); return true; }
                stats.recordGift(user, coins);
                reply(sender, "Kaydedildi: " + user + " +" + coins, NamedTextColor.LIGHT_PURPLE);
            }
            case "wins" -> reply(sender, "Toplam zafer: " + stats.getWins(), NamedTextColor.GOLD);
            case "cleargifters" -> { stats.resetGifters(); reply(sender, "Hediye listesi sifirlandi", NamedTextColor.YELLOW); }
            case "hud" -> {
                if (!(sender instanceof Player p)) { reply(sender, "Sadece oyuncu", NamedTextColor.RED); return true; }
                hud.showTo(p);
                reply(sender, "HUD goruntulendi", NamedTextColor.GREEN);
            }
            case "penalty" -> handlePenalty(sender, args);
            case "bot" -> handleBot(sender, args);
            case "rebuild" -> handleRebuild(sender, args);
            case "walls" -> handleWalls(sender);
            default -> reply(sender, "Bilinmeyen alt komut: " + sub, NamedTextColor.RED);
        }
        return true;
    }

    /**
     * /arena rebuild [legacy_size]
     * Eski (legacy_size x legacy_size, default 16) alandaki yeni bounds disi
     * iron/gold/diamond ve wall material bloklarini siler, yeni bounds'a duvarlari kurar.
     */
    private void handleRebuild(CommandSender sender, String[] args) {
        int legacy = 16;
        if (args.length >= 2) {
            try { legacy = Integer.parseInt(args[1]); }
            catch (NumberFormatException ignored) {}
        }
        int cleared = 0;
        int builtWall = 0;
        int yLo = config.minY - 1;
        int yHi = config.maxY + 1;

        // 1) Eski iç alanda (0..legacy-1) yeni inner disinda kalan tier bloklarini sil
        for (int x = 0; x < legacy; x++) {
            for (int z = 0; z < legacy; z++) {
                for (int y = config.minY; y <= config.maxY; y++) {
                    if (x >= config.minX && x <= config.maxX && z >= config.minZ && z <= config.maxZ) continue;
                    Block b = config.world.getBlockAt(x, y, z);
                    Material m = b.getType();
                    if (m == Material.IRON_BLOCK || m == Material.GOLD_BLOCK || m == Material.DIAMOND_BLOCK
                            || m == config.wallMaterial) {
                        b.setType(Material.AIR, false);
                        cleared++;
                    }
                }
            }
        }
        // 2) Eski cevreleyen duvarlari sil (legacy cercevesi)
        for (int y = yLo; y <= yHi; y++) {
            for (int i = -1; i <= legacy; i++) {
                int[][] ring = {{-1, i}, {legacy, i}, {i, -1}, {i, legacy}};
                for (int[] p : ring) {
                    int x = p[0], z = p[1];
                    Block b = config.world.getBlockAt(x, y, z);
                    if (b.getType() == config.wallMaterial) {
                        b.setType(Material.AIR, false);
                        cleared++;
                    }
                }
            }
        }
        // 3) Yeni inner bounds etrafina duvarlari kur
        int nxMin = config.minX - 1, nxMax = config.maxX + 1;
        int nzMin = config.minZ - 1, nzMax = config.maxZ + 1;
        for (int y = yLo; y <= yHi; y++) {
            for (int x = nxMin; x <= nxMax; x++) {
                for (int z : new int[]{nzMin, nzMax}) {
                    Block b = config.world.getBlockAt(x, y, z);
                    if (b.getType() != config.wallMaterial) {
                        b.setType(config.wallMaterial, false);
                        builtWall++;
                    }
                }
            }
            for (int z = nzMin + 1; z <= nzMax - 1; z++) {
                for (int x : new int[]{nxMin, nxMax}) {
                    Block b = config.world.getBlockAt(x, y, z);
                    if (b.getType() != config.wallMaterial) {
                        b.setType(config.wallMaterial, false);
                        builtWall++;
                    }
                }
            }
        }
        // 4) Zemini (y = minY - 1) de camdan tabanla
        for (int x = nxMin; x <= nxMax; x++) {
            for (int z = nzMin; z <= nzMax; z++) {
                Block b = config.world.getBlockAt(x, config.minY - 1, z);
                if (b.getType() != config.wallMaterial) {
                    b.setType(config.wallMaterial, false);
                    builtWall++;
                }
            }
        }
        reply(sender, "Temizlenen: " + cleared + " blok | Yeni duvar: " + builtWall + " blok",
                NamedTextColor.GREEN);
    }

    /**
     * /arena walls — arena etrafindaki genis bir bolgedeki TUM wallMaterial bloklarini
     * siler, sonra sadece guncel inner bounds'a gore duvar + taban kurar.
     * Eski 10x10 vs 16x16 artiklarini tamamen temizler.
     */
    private void handleWalls(CommandSender sender) {
        int margin = 6;
        int cleared = 0;
        for (int x = config.minX - margin; x <= config.maxX + margin; x++) {
            for (int z = config.minZ - margin; z <= config.maxZ + margin; z++) {
                for (int y = config.minY - margin; y <= config.maxY + margin; y++) {
                    Block b = config.world.getBlockAt(x, y, z);
                    if (b.getType() == config.wallMaterial) {
                        b.setType(Material.AIR, false);
                        cleared++;
                    }
                }
            }
        }
        int built = 0;
        int yLo = config.minY - 1;
        int yHi = config.maxY + 1;
        int nxMin = config.minX - 1, nxMax = config.maxX + 1;
        int nzMin = config.minZ - 1, nzMax = config.maxZ + 1;
        // 4 yan duvar
        for (int y = yLo; y <= yHi; y++) {
            for (int x = nxMin; x <= nxMax; x++) {
                config.world.getBlockAt(x, y, nzMin).setType(config.wallMaterial, false); built++;
                config.world.getBlockAt(x, y, nzMax).setType(config.wallMaterial, false); built++;
            }
            for (int z = nzMin + 1; z <= nzMax - 1; z++) {
                config.world.getBlockAt(nxMin, y, z).setType(config.wallMaterial, false); built++;
                config.world.getBlockAt(nxMax, y, z).setType(config.wallMaterial, false); built++;
            }
        }
        // Taban
        for (int x = nxMin; x <= nxMax; x++) {
            for (int z = nzMin; z <= nzMax; z++) {
                config.world.getBlockAt(x, config.minY - 1, z).setType(config.wallMaterial, false); built++;
            }
        }
        reply(sender, "Cam temizlenen: " + cleared + " | Duvar+taban kuruldu: " + built,
                NamedTextColor.GREEN);
    }

    private Player resolvePenaltyTarget(CommandSender sender, String[] args, int nameIndex) {
        if (args.length > nameIndex) {
            return Bukkit.getPlayerExact(args[nameIndex]);
        }
        if (sender instanceof Player p) return p;
        return Bukkit.getOnlinePlayers().stream().findFirst().orElse(null);
    }

    private void handlePenalty(CommandSender sender, String[] args) {
        if (args.length < 2) {
            reply(sender, "Kullanim: /arena penalty <prison|gauntlet|end> [user]", NamedTextColor.RED);
            return;
        }
        String type = args[1].toLowerCase(Locale.ROOT);
        Player target;
        if (args.length >= 3) {
            target = Bukkit.getPlayerExact(args[2]);
            if (target == null) { reply(sender, "Oyuncu bulunamadi: " + args[2], NamedTextColor.RED); return; }
        } else if (sender instanceof Player p) {
            target = p;
        } else {
            target = Bukkit.getOnlinePlayers().stream().findFirst().orElse(null);
            if (target == null) { reply(sender, "Online oyuncu yok", NamedTextColor.RED); return; }
        }
        switch (type) {
            case "prison", "jail", "hapis" -> {
                boolean ok = penalty.startPrison(target);
                reply(sender, ok ? "Hapis baslatildi: " + target.getName() : "Oyuncu zaten cezali", NamedTextColor.LIGHT_PURPLE);
            }
            case "gauntlet", "yem", "canavar" -> {
                boolean ok = penalty.startGauntlet(target);
                reply(sender, ok ? "Gauntlet baslatildi: " + target.getName() : "Oyuncu zaten cezali", NamedTextColor.LIGHT_PURPLE);
            }
            case "end", "stop", "release" -> {
                penalty.endPenalty(target, true, "Elle serbest birakildi");
                reply(sender, "Ceza sonlandirildi: " + target.getName(), NamedTextColor.GREEN);
            }
            default -> reply(sender, "Bilinmeyen ceza: " + type, NamedTextColor.RED);
        }
    }

    private void handleBot(CommandSender sender, String[] args) {
        if (args.length < 2) {
            reply(sender, "Kullanim: /arena bot <start [bps] [tip] [isim]|summon <isim>|stop|status|list|watch|unwatch>",
                    NamedTextColor.RED);
            return;
        }
        String sub = args[1].toLowerCase(Locale.ROOT);
        switch (sub) {
            case "start" -> {
                int bps = config.botDefaultBps;
                String type = config.botDefaultType;
                String name = config.botDefaultName;
                if (args.length >= 3) {
                    try { bps = Integer.parseInt(args[2]); }
                    catch (NumberFormatException e) { reply(sender, "Gecersiz rate", NamedTextColor.RED); return; }
                }
                if (args.length >= 4) type = args[3];
                if (args.length >= 5) name = args[4];
                HelperBot b = botPool.spawn(bps, type, name);
                reply(sender, b != null
                                ? "Bot eklendi: " + name + " [" + type + " @ " + bps + " bps] — toplam: " + botPool.size()
                                : "Bot eklenemedi (limit/hata)",
                        b != null ? NamedTextColor.GREEN : NamedTextColor.RED);
            }
            case "summon", "rename" -> {
                if (args.length < 3) { reply(sender, "Kullanim: /arena bot summon <isim>", NamedTextColor.RED); return; }
                String name = args[2];
                HelperBot b = botPool.summonFromGift(name);
                reply(sender, b != null
                                ? "Bot cagrildi: " + name + " — toplam: " + botPool.size()
                                : "Bot cagrilamadi",
                        b != null ? NamedTextColor.LIGHT_PURPLE : NamedTextColor.RED);
            }
            case "stop" -> {
                int n = botPool.stopAll();
                reply(sender, n > 0 ? n + " bot durduruldu" : "Bot yok",
                        n > 0 ? NamedTextColor.YELLOW : NamedTextColor.GRAY);
            }
            case "status", "list" -> {
                var all = botPool.all();
                if (all.isEmpty()) { reply(sender, "Aktif bot yok", NamedTextColor.AQUA); return; }
                StringBuilder sb = new StringBuilder("Aktif bot (" + all.size() + "):");
                for (HelperBot bb : all) {
                    sb.append(" [").append(bb.displayName()).append("/").append(bb.type()).append("]");
                }
                reply(sender, sb.toString(), NamedTextColor.AQUA);
            }
            case "watch", "pov" -> {
                Player p = resolvePenaltyTarget(sender, args, 2);
                if (p == null) { reply(sender, "Online oyuncu yok", NamedTextColor.RED); return; }
                boolean ok = botPool.watch(p);
                reply(sender, ok ? "Bot POV: " + p.getName() + " (son bot)"
                                 : "Aktif bot yok", NamedTextColor.GREEN);
            }
            case "unwatch", "exit" -> {
                Player p = resolvePenaltyTarget(sender, args, 2);
                if (p == null) { reply(sender, "Online oyuncu yok", NamedTextColor.RED); return; }
                boolean ok = botPool.unwatch(p);
                reply(sender, ok ? "POV kapatildi: " + p.getName()
                                 : "Zaten POV'da degil", NamedTextColor.YELLOW);
            }
            default -> reply(sender, "Bilinmeyen bot alt komutu: " + sub, NamedTextColor.RED);
        }
    }

    private TierDefinition findTier(String name) {
        for (TierDefinition t : config.tiers) if (t.name().equalsIgnoreCase(name)) return t;
        return null;
    }

    private int clearArena() {
        int n = 0;
        for (int x = config.minX; x <= config.maxX; x++)
            for (int y = config.minY; y <= config.maxY; y++)
                for (int z = config.minZ; z <= config.maxZ; z++) {
                    config.world.getBlockAt(x, y, z).setType(Material.AIR, false); n++;
                }
        return n;
    }

    private int fillTier(TierDefinition t) {
        int n = 0;
        for (int x = config.minX; x <= config.maxX; x++)
            for (int y = t.yMin(); y <= t.yMax(); y++)
                for (int z = config.minZ; z <= config.maxZ; z++) {
                    config.world.getBlockAt(x, y, z).setType(t.block(), false); n++;
                }
        return n;
    }

    private int fillArena(int pct) {
        int n = 0, totalCap = 0;
        for (TierDefinition t : config.tiers)
            totalCap += config.sizeX * config.sizeZ * (t.yMax() - t.yMin() + 1);
        int target = (int) ((long) totalCap * pct / 100);
        outer:
        for (TierDefinition t : config.tiers) {
            for (int y = t.yMin(); y <= t.yMax(); y++)
                for (int x = config.minX; x <= config.maxX; x++)
                    for (int z = config.minZ; z <= config.maxZ; z++) {
                        if (n >= target) break outer;
                        config.world.getBlockAt(x, y, z).setType(t.block(), false); n++;
                    }
        }
        return n;
    }

    /** TNT arenanin yukarisindan dusurulur. Nuke merkezden yuksek dusurulur. */
    private void spawnTnt(String tier) {
        int x, z;
        int yDrop = config.maxY + 10; // her zaman yukaridan
        int fuse;
        if ("nuke".equalsIgnoreCase(tier)) {
            x = (config.minX + config.maxX) / 2;
            z = (config.minZ + config.maxZ) / 2;
            Location loc = new Location(config.world, x + 0.5, yDrop, z + 0.5);
            config.world.spawn(loc, TNTPrimed.class, t -> {
                t.setFuseTicks(60);
                t.addScoreboardTag("box_nuke");
            });
            return;
        }
        if ("meteor".equalsIgnoreCase(tier)) {
            spawnMeteorStorm(50);
            return;
        }
        x = config.minX + 1 + random.nextInt(Math.max(1, config.sizeX - 2));
        z = config.minZ + 1 + random.nextInt(Math.max(1, config.sizeZ - 2));
        fuse = tier.equalsIgnoreCase("rain") ? 35 : 50;
        Location loc = new Location(config.world, x + 0.5, yDrop, z + 0.5);
        final int fuseTicks = fuse;
        config.world.spawn(loc, TNTPrimed.class, t -> {
            t.setFuseTicks(fuseTicks);
            if (!"normal".equalsIgnoreCase(tier)) t.addScoreboardTag("box_" + tier.toLowerCase());
        });
    }

    private void spawnMeteorStorm(int count) {
        int yDrop = config.maxY + 25;
        for (int i = 0; i < count; i++) {
            int x = config.minX + random.nextInt(Math.max(1, config.sizeX));
            int z = config.minZ + random.nextInt(Math.max(1, config.sizeZ));
            int delay = i * 2;
            Location loc = new Location(config.world, x + 0.5, yDrop + random.nextInt(8), z + 0.5);
            Bukkit.getScheduler().runTaskLater(plugin, () -> {
                var fb = config.world.spawn(loc, org.bukkit.entity.Fireball.class, f -> {
                    f.setYield(2.5f);
                    f.setIsIncendiary(true);
                    f.setDirection(new org.bukkit.util.Vector(0, -1, 0));
                    f.setVelocity(new org.bukkit.util.Vector(0, -1.2, 0));
                    f.addScoreboardTag("box_meteor");
                });
            }, delay);
        }
    }
}
