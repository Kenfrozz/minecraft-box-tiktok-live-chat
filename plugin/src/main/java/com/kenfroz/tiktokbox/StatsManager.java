package com.kenfroz.tiktokbox;

import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.plugin.java.JavaPlugin;

import java.io.File;
import java.io.IOException;
import java.util.*;

public class StatsManager {
    private final JavaPlugin plugin;
    private final File file;
    private YamlConfiguration data;

    public StatsManager(JavaPlugin plugin) {
        this.plugin = plugin;
        this.file = new File(plugin.getDataFolder(), "stats.yml");
        if (!plugin.getDataFolder().exists()) plugin.getDataFolder().mkdirs();
        if (!file.exists()) {
            try { file.createNewFile(); } catch (IOException e) { plugin.getLogger().warning(e.getMessage()); }
        }
        this.data = YamlConfiguration.loadConfiguration(file);
    }

    public int getWins() { return data.getInt("wins", 0); }

    public void incrementWins() {
        data.set("wins", getWins() + 1);
        save();
    }

    public void recordGift(String username, long coins) {
        String path = "gifters." + username.replace(".", "_DOT_");
        long current = data.getLong(path, 0);
        data.set(path, current + coins);
        save();
    }

    public List<Map.Entry<String, Long>> topGifters(int limit) {
        Map<String, Object> raw = data.getConfigurationSection("gifters") == null
                ? Collections.emptyMap()
                : data.getConfigurationSection("gifters").getValues(false);
        List<Map.Entry<String, Long>> list = new ArrayList<>();
        for (Map.Entry<String, Object> e : raw.entrySet()) {
            String user = e.getKey().replace("_DOT_", ".");
            long coins = ((Number) e.getValue()).longValue();
            list.add(new AbstractMap.SimpleEntry<>(user, coins));
        }
        list.sort((a, b) -> Long.compare(b.getValue(), a.getValue()));
        return list.subList(0, Math.min(limit, list.size()));
    }

    public void resetGifters() {
        data.set("gifters", null);
        save();
    }

    public void save() {
        try { data.save(file); } catch (IOException e) { plugin.getLogger().warning(e.getMessage()); }
    }
}
