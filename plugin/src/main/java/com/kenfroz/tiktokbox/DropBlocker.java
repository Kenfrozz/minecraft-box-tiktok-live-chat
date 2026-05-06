package com.kenfroz.tiktokbox;

import org.bukkit.block.Block;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.block.BlockBreakEvent;
import org.bukkit.event.block.BlockDropItemEvent;
import org.bukkit.event.entity.EntityExplodeEvent;

import java.util.Iterator;

public class DropBlocker implements Listener {
    private final ArenaConfig config;

    public DropBlocker(ArenaConfig config) {
        this.config = config;
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onBreak(BlockBreakEvent event) {
        event.setDropItems(false);
        event.setExpToDrop(0);
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onBlockDrop(BlockDropItemEvent event) {
        event.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onExplode(EntityExplodeEvent event) {
        event.setYield(0f);
        // Arena duvar materyali (cam/bedrock/ne olursa) patlamalardan korunur
        Iterator<Block> it = event.blockList().iterator();
        while (it.hasNext()) {
            if (it.next().getType() == config.wallMaterial) it.remove();
        }
    }
}
