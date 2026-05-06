package com.kenfroz.tiktokbox;

import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;
import net.kyori.adventure.text.format.TextDecoration;
import org.bukkit.Bukkit;
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.SoundCategory;
import org.bukkit.attribute.Attribute;
import org.bukkit.block.Block;
import org.bukkit.entity.Entity;
import org.bukkit.entity.EntityType;
import org.bukkit.entity.Mob;
import org.bukkit.entity.Player;
import org.bukkit.entity.Villager;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.CreatureSpawnEvent;
import org.bukkit.event.entity.EntityDamageEvent;
import org.bukkit.plugin.java.JavaPlugin;
import org.bukkit.scheduler.BukkitRunnable;
import org.bukkit.util.Vector;

import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;

public class HelperBot {
    /** Blok basina hareket hizi (blok/tick). 0.30 ~ 6 blok/sn, dogal yuruyus hizi. */
    private static final double MOVE_SPEED = 0.30;
    /** Bot hedef blogun kac blok ustunde hover edecek (yerlestirme pozisyonu). */
    private static final double APPROACH_HEIGHT = 1.6;
    /** Hedefe bu kadar yakinsa ulasti say. */
    private static final double ARRIVE_DIST = 0.25;

    private final JavaPlugin plugin;
    private final ArenaConfig config;
    private Mob bot;
    private UUID botId;
    private BukkitRunnable task;
    private int blocksPerSecond = 2;
    private String entityType = "villager";
    private String displayName = "Usta";
    private final Map<UUID, GameMode> watchers = new HashMap<>();

    private enum State { IDLE, MOVING, PLACING, WAITING }
    private State state = State.IDLE;
    private Block targetBlock;
    private Material targetMaterial;
    private Location moveTarget;
    private int waitTicksLeft;

    public HelperBot(JavaPlugin plugin, ArenaConfig config) {
        this.plugin = plugin;
        this.config = config;
    }

    public boolean isRunning() {
        return botId != null;
    }

    private boolean ensureBotValid() {
        if (botId == null) return false;
        if (bot != null && bot.isValid() && !bot.isDead()) return true;
        // Wrapper geçersiz (chunk reload / new wrapper gerekli) — UUID ile yeniden bul.
        Entity e = Bukkit.getEntity(botId);
        if (e instanceof Mob m && !m.isDead()) {
            this.bot = m;
            return m.isValid();
        }
        return false;
    }

    public int rate() { return blocksPerSecond; }
    public String type() { return entityType; }

    public boolean start(int bps, String typeName) {
        return start(bps, typeName, this.displayName);
    }

    public boolean start(int bps, String typeName, String name) {
        if (isRunning()) return false;
        this.blocksPerSecond = Math.max(1, Math.min(20, bps));
        this.entityType = (typeName == null ? "villager" : typeName).toLowerCase(Locale.ROOT);
        this.displayName = (name == null || name.isBlank()) ? this.displayName : name;

        EntityType type;
        try {
            type = EntityType.valueOf(this.entityType.toUpperCase(Locale.ROOT));
        } catch (Exception e) {
            plugin.getLogger().warning("Bilinmeyen bot tipi: " + this.entityType + ", villager kullaniliyor");
            type = EntityType.VILLAGER;
            this.entityType = "villager";
        }

        int cx = (config.minX + config.maxX) / 2;
        int cz = (config.minZ + config.maxZ) / 2;
        Location spawn = new Location(config.world, cx + 0.5, config.maxY + 2, cz + 0.5);

        Entity e;
        try {
            e = config.world.spawnEntity(spawn, type, CreatureSpawnEvent.SpawnReason.CUSTOM);
        } catch (Exception ex) {
            plugin.getLogger().warning("Bot spawn hatasi: " + ex.getMessage());
            return false;
        }
        if (!(e instanceof Mob mob)) {
            e.remove();
            plugin.getLogger().warning("Bot tipi Mob degil: " + this.entityType);
            return false;
        }

        mob.customName(Component.text(this.displayName, NamedTextColor.AQUA).decorate(TextDecoration.BOLD));
        mob.setCustomNameVisible(true);
        mob.setAI(false);
        mob.setInvulnerable(true);
        mob.setGlowing(config.botGlowing);
        mob.setPersistent(true);
        mob.setRemoveWhenFarAway(false);
        mob.setSilent(true);
        mob.setGravity(false);
        mob.addScoreboardTag("box_helper_bot");
        // TNT/patlama knockback'ini engelle.
        var kbRes = mob.getAttribute(Attribute.KNOCKBACK_RESISTANCE);
        if (kbRes != null) kbRes.setBaseValue(1.0);
        try {
            var exRes = mob.getAttribute(Attribute.EXPLOSION_KNOCKBACK_RESISTANCE);
            if (exRes != null) exRes.setBaseValue(1.0);
        } catch (Exception ignore) {}

        if (mob instanceof Villager v) {
            try {
                v.setProfession(Villager.Profession.MASON);
                v.setVillagerLevel(5);
            } catch (Exception ignore) {}
        }

        this.bot = mob;
        this.botId = mob.getUniqueId();
        this.state = State.IDLE;
        this.targetBlock = null;
        this.moveTarget = null;
        this.task = new BukkitRunnable() {
            @Override
            public void run() {
                if (botId == null) { cancel(); return; }
                if (!ensureBotValid()) {
                    // Entity ya unloaded (chunk) ya da gercekten silinmis.
                    // Unloaded ise sonraki tick'te geri gelir; silinmis ise kalici.
                    return;
                }
                try { tick(); } catch (Exception ex) {
                    plugin.getLogger().warning("Bot tick hatasi: " + ex.getMessage());
                }
            }
        };
        // Her tick calissin — state machine yumusak hareket saglayacak.
        this.task.runTaskTimer(plugin, 10L, 1L);
        return true;
    }

    public boolean start(int bps) { return start(bps, entityType); }

    public boolean stop() {
        boolean removed = false;
        for (var entry : new HashMap<>(watchers).entrySet()) {
            Player p = Bukkit.getPlayer(entry.getKey());
            if (p != null) unwatch(p);
            else watchers.remove(entry.getKey());
        }
        if (task != null) {
            try { task.cancel(); } catch (Exception ignore) {}
            task = null;
        }
        if (bot != null) {
            try {
                bot.remove();
                removed = true;
            } catch (Exception ignore) {}
            bot = null;
        }
        // UUID ile de bul ve sil (wrapper geçersiz olmuş olabilir).
        if (botId != null) {
            Entity e = Bukkit.getEntity(botId);
            if (e != null) { e.remove(); removed = true; }
            botId = null;
        }
        // Ayrıca tag ile de temizle (guvenlik).
        for (Entity e : config.world.getEntities()) {
            if (e.getScoreboardTags().contains("box_helper_bot")) e.remove();
        }
        state = State.IDLE;
        targetBlock = null;
        moveTarget = null;
        return removed;
    }

    /** Hediye geldiginde bot ismini guncelle. Bot yoksa varsayilan ayarlarla spawn et. */
    public boolean summon(String name, int defaultBps, String defaultType) {
        String safe = (name == null || name.isBlank()) ? "anonim" : name;
        if (isRunning()) {
            setDisplayName(safe);
            return false;
        }
        return start(defaultBps, defaultType, safe);
    }

    public void setDisplayName(String name) {
        if (name == null || name.isBlank()) return;
        this.displayName = name;
        if (bot != null && bot.isValid()) {
            bot.customName(Component.text(name, NamedTextColor.AQUA).decorate(TextDecoration.BOLD));
            bot.setCustomNameVisible(true);
        }
    }

    public String displayName() { return displayName; }
    public Mob entity() { return bot; }
    public UUID botUuid() { return botId; }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onDamage(EntityDamageEvent event) {
        if (event.getEntity().getScoreboardTags().contains("box_helper_bot")) {
            event.setCancelled(true);
        }
    }

    public boolean watch(Player p) {
        if (!isRunning()) return false;
        if (!watchers.containsKey(p.getUniqueId())) {
            watchers.put(p.getUniqueId(), p.getGameMode());
        }
        p.setGameMode(GameMode.SPECTATOR);
        Bukkit.getScheduler().runTaskLater(plugin, () -> {
            if (p.isOnline() && isRunning()) p.setSpectatorTarget(bot);
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

    public boolean isWatching(Player p) {
        return watchers.containsKey(p.getUniqueId());
    }

    /** Her tick calisir. */
    private void tick() {
        // Hedef bir baskasi tarafindan doldurulmussa vazgec.
        if ((state == State.MOVING || state == State.PLACING)
                && targetBlock != null
                && targetBlock.getType() == targetMaterial) {
            state = State.WAITING;
            waitTicksLeft = 4;
        }
        switch (state) {
            case IDLE -> findNextTarget();
            case MOVING -> moveStep();
            case PLACING -> placeNow();
            case WAITING -> {
                // Hedefe dogru bakmaya devam et (POV'da sabit fokus hissi).
                faceTarget();
                if (--waitTicksLeft <= 0) state = State.IDLE;
            }
        }
    }

    private void findNextTarget() {
        Location from = bot.getLocation();
        double fx = from.getX(), fz = from.getZ();
        // Alt tier'dan baslayarak, her tier'da Y katmani katmani (yMin'den yukari),
        // her katmanda bota en yakin bos blogu sec. Boylece:
        //   - hic bir zaman bir altindaki katmani geride birakip ustune cikmaz
        //   - ayni katman icinde komsu bloklari doldura doldura gider
        for (TierDefinition t : config.tiers) {
            Material target = t.block();
            for (int y = t.yMin(); y <= t.yMax(); y++) {
                Block best = null;
                double bestD = Double.MAX_VALUE;
                for (int x = config.minX; x <= config.maxX; x++) {
                    for (int z = config.minZ; z <= config.maxZ; z++) {
                        Block b = config.world.getBlockAt(x, y, z);
                        if (b.getType() == target) continue;
                        double dx = (x + 0.5) - fx;
                        double dz = (z + 0.5) - fz;
                        double d = dx * dx + dz * dz;
                        if (d < bestD) {
                            bestD = d;
                            best = b;
                        }
                    }
                }
                if (best != null) {
                    this.targetBlock = best;
                    this.targetMaterial = target;
                    this.moveTarget = new Location(config.world,
                            best.getX() + 0.5,
                            best.getY() + APPROACH_HEIGHT,
                            best.getZ() + 0.5);
                    this.state = State.MOVING;
                    return;
                }
            }
        }
        // Arena dolu — kisa bekle, tekrar tara.
        state = State.WAITING;
        waitTicksLeft = 20;
    }

    private void moveStep() {
        if (bot == null || !bot.isValid() || moveTarget == null) {
            state = State.IDLE;
            return;
        }
        Location cur = bot.getLocation();
        Vector toward = moveTarget.toVector().subtract(cur.toVector());
        double dist = toward.length();

        // Her zaman hedef bloga bak — POV'da kamera koyulacak yere fokuslu.
        float[] yp = yawPitchToBlockCenter(cur);

        if (dist <= ARRIVE_DIST + MOVE_SPEED) {
            Location at = moveTarget.clone();
            at.setYaw(yp[0]); at.setPitch(yp[1]);
            bot.teleport(at);
            state = State.PLACING;
            return;
        }
        Vector step = toward.clone().normalize().multiply(MOVE_SPEED);
        Location next = cur.clone().add(step);
        next.setYaw(yp[0]); next.setPitch(yp[1]);
        bot.teleport(next);
    }

    private void placeNow() {
        if (bot == null || !bot.isValid() || targetBlock == null) {
            state = State.IDLE; return;
        }
        // Son pozisyonda hedefe tam bak
        faceTarget();
        // Kol salla (oyuncu gibi)
        try { bot.swingMainHand(); } catch (Exception ignore) {}

        Block b = targetBlock;
        if (b.getType() != targetMaterial) {
            b.setType(targetMaterial, false);
            Location center = b.getLocation().add(0.5, 0.5, 0.5);
            config.world.spawnParticle(Particle.HAPPY_VILLAGER, center, 5, 0.25, 0.25, 0.25, 0.01);
            var placeSound = b.getBlockData().getSoundGroup().getPlaceSound();
            config.world.playSound(b.getLocation(), placeSound, SoundCategory.BLOCKS, 1f, 1f);
        }

        // bps'e gore kisa duraklama — insanvari 'nefes'.
        this.waitTicksLeft = Math.max(1, 20 / blocksPerSecond - 3);
        this.state = State.WAITING;
    }

    /** Bot'un bakisini mevcut konumdan hedef blok merkezine yaw+pitch olarak ayarlar. */
    private void faceTarget() {
        if (bot == null || !bot.isValid() || targetBlock == null) return;
        Location cur = bot.getLocation();
        float[] yp = yawPitchToBlockCenter(cur);
        cur.setYaw(yp[0]); cur.setPitch(yp[1]);
        bot.teleport(cur);
    }

    /** Verilen konumdan hedef blok merkezine bakan yaw/pitch degerleri. */
    private float[] yawPitchToBlockCenter(Location from) {
        Vector to = targetBlock.getLocation().add(0.5, 0.5, 0.5).toVector()
                .subtract(from.toVector());
        return vectorToYawPitch(to);
    }

    private static float[] vectorToYawPitch(Vector v) {
        double dx = v.getX(), dy = v.getY(), dz = v.getZ();
        double horiz = Math.sqrt(dx * dx + dz * dz);
        if (horiz < 1e-6 && Math.abs(dy) < 1e-6) return new float[]{0f, 0f};
        float yaw = (float) Math.toDegrees(Math.atan2(-dx, dz));
        float pitch = (float) Math.toDegrees(-Math.atan2(dy, horiz));
        return new float[]{yaw, pitch};
    }
}
