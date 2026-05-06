package com.kenfroz.tiktokbox;

import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;
import net.kyori.adventure.text.format.TextDecoration;
import org.bukkit.Bukkit;
import org.bukkit.entity.Player;
import org.bukkit.scoreboard.Criteria;
import org.bukkit.scoreboard.DisplaySlot;
import org.bukkit.scoreboard.Objective;
import org.bukkit.scoreboard.Scoreboard;
import org.bukkit.scoreboard.ScoreboardManager;
import org.bukkit.scoreboard.Team;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

public class HudManager {
    private final StatsManager stats;
    private final Scoreboard board;
    private final Objective obj;
    private final List<String> teamNames = new ArrayList<>();

    public HudManager(StatsManager stats) {
        this.stats = stats;
        ScoreboardManager sm = Bukkit.getScoreboardManager();
        this.board = sm.getNewScoreboard();
        Component title = Component.text("♛ ", NamedTextColor.GOLD, TextDecoration.BOLD)
                .append(Component.text("KENFROZ", NamedTextColor.LIGHT_PURPLE, TextDecoration.BOLD))
                .append(Component.text(" ♛", NamedTextColor.GOLD, TextDecoration.BOLD));
        this.obj = board.registerNewObjective(
                "tiktokbox",
                Criteria.DUMMY,
                title
        );
        obj.setDisplaySlot(DisplaySlot.SIDEBAR);
        buildTeams();
    }

    private void buildTeams() {
        // 10 dinamik satir icin team + entry (entry = renk kodu uniqueligi)
        String[] colors = {
            "§0","§1","§2","§3","§4","§5","§6","§7","§8","§9","§a","§b","§c","§d","§e","§f"
        };
        for (int i = 0; i < 12; i++) {
            String name = "hud_" + i;
            Team t = board.getTeam(name);
            if (t == null) t = board.registerNewTeam(name);
            String entry = colors[i] + "§r"; // her satir unique
            t.addEntry(entry);
            teamNames.add(entry);
        }
    }

    public void update(int filled, int total, boolean countdownActive, int countdownLeft) {
        int pct = total == 0 ? 0 : (int) ((long) filled * 100 / total);
        List<Component> lines = new ArrayList<>();
        lines.add(Component.text("◆ Kazanma: ", NamedTextColor.GRAY)
                .append(Component.text(stats.getWins(), NamedTextColor.GOLD, TextDecoration.BOLD)));
        lines.add(Component.text("◆ Doluluk: ", NamedTextColor.GRAY)
                .append(Component.text("%" + pct, pct >= 90 ? NamedTextColor.GREEN
                        : pct >= 50 ? NamedTextColor.YELLOW : NamedTextColor.RED,
                        TextDecoration.BOLD)));
        if (countdownActive) {
            lines.add(Component.text("⏱ Zafere: ", NamedTextColor.GRAY)
                    .append(Component.text(countdownLeft + "s", NamedTextColor.AQUA, TextDecoration.BOLD)));
        }
        lines.add(Component.text("                 ", NamedTextColor.DARK_GRAY, TextDecoration.STRIKETHROUGH));
        lines.add(Component.text("❤ Top 5 Hediye", NamedTextColor.LIGHT_PURPLE, TextDecoration.BOLD));

        List<Map.Entry<String, Long>> top = stats.topGifters(5);
        if (top.isEmpty()) {
            lines.add(Component.text("  - henuz yok -", NamedTextColor.DARK_GRAY));
        } else {
            NamedTextColor[] rankColors = {
                NamedTextColor.GOLD, NamedTextColor.YELLOW,
                NamedTextColor.WHITE, NamedTextColor.GRAY, NamedTextColor.DARK_GRAY
            };
            for (int i = 0; i < top.size(); i++) {
                Map.Entry<String, Long> e = top.get(i);
                String user = e.getKey();
                if (user.length() > 12) user = user.substring(0, 12);
                lines.add(Component.text((i+1) + ". ", rankColors[i])
                        .append(Component.text(user, NamedTextColor.WHITE))
                        .append(Component.text(" " + e.getValue(), NamedTextColor.AQUA)));
            }
        }

        // Clear old scores
        for (String e : board.getEntries()) board.resetScores(e);

        // Write new lines (score determines order; higher = top)
        int n = lines.size();
        for (int i = 0; i < n && i < teamNames.size(); i++) {
            String entry = teamNames.get(i);
            Team team = board.getTeam("hud_" + i);
            team.prefix(lines.get(i));
            team.suffix(Component.empty());
            obj.getScore(entry).setScore(n - i);
        }
    }

    public void showTo(Player p) { p.setScoreboard(board); }
    public void hideAll() {
        Scoreboard main = Bukkit.getScoreboardManager().getMainScoreboard();
        Bukkit.getOnlinePlayers().forEach(p -> p.setScoreboard(main));
    }
}
