package com.kenfroz.tiktokbox;

import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerJoinEvent;

public class HudJoinListener implements Listener {
    private final HudManager hud;

    public HudJoinListener(HudManager hud) { this.hud = hud; }

    @EventHandler
    public void onJoin(PlayerJoinEvent event) {
        hud.showTo(event.getPlayer());
    }
}
