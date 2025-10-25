"""
WebSocket connection manager
"""
import asyncio
import json
from typing import Dict, Set
from fastapi import WebSocket
from loguru import logger


class WebSocketManager:
    """Manages WebSocket connections"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_tasks: Dict[str, asyncio.Task] = {}
        
    async def connect(self, websocket: WebSocket, session_id: str):
        """Accept and register a new WebSocket connection"""
        await websocket.accept()
        self.active_connections[session_id] = websocket
        logger.info(f"WebSocket connected: {session_id}")
        
    def disconnect(self, session_id: str):
        """Remove a WebSocket connection"""
        if session_id in self.active_connections:
            del self.active_connections[session_id]
            logger.info(f"WebSocket disconnected: {session_id}")
            
        # Cancel any running tasks
        if session_id in self.connection_tasks:
            self.connection_tasks[session_id].cancel()
            del self.connection_tasks[session_id]
    
    async def send_text(self, session_id: str, message: str):
        """Send text message to a specific client"""
        if session_id in self.active_connections:
            websocket = self.active_connections[session_id]
            try:
                await websocket.send_text(message)
            except Exception as e:
                logger.error(f"Error sending message to {session_id}: {e}")
                self.disconnect(session_id)
    
    async def send_json(self, session_id: str, data: dict):
        """Send JSON data to a specific client"""
        if session_id in self.active_connections:
            websocket = self.active_connections[session_id]
            try:
                await websocket.send_json(data)
            except Exception as e:
                logger.error(f"Error sending JSON to {session_id}: {e}")
                self.disconnect(session_id)
    
    async def send_bytes(self, session_id: str, data: bytes):
        """Send binary data to a specific client"""
        if session_id in self.active_connections:
            websocket = self.active_connections[session_id]
            try:
                await websocket.send_bytes(data)
            except Exception as e:
                logger.error(f"Error sending bytes to {session_id}: {e}")
                self.disconnect(session_id)
    
    async def broadcast_json(self, data: dict, exclude: Set[str] = None):
        """Broadcast JSON data to all connected clients"""
        exclude = exclude or set()
        disconnected = []
        
        for session_id, websocket in self.active_connections.items():
            if session_id not in exclude:
                try:
                    await websocket.send_json(data)
                except Exception as e:
                    logger.error(f"Error broadcasting to {session_id}: {e}")
                    disconnected.append(session_id)
        
        # Clean up disconnected clients
        for session_id in disconnected:
            self.disconnect(session_id)
    
    def get_active_connections(self) -> int:
        """Get number of active connections"""
        return len(self.active_connections)
    
    def is_connected(self, session_id: str) -> bool:
        """Check if a session is connected"""
        return session_id in self.active_connections
    
    async def heartbeat(self, session_id: str, interval: int = 60):
        """
        Send periodic heartbeat to detect disconnections
        
        Args:
            session_id: Session identifier
            interval: Heartbeat interval in seconds
        """
        consecutive_failures = 0
        max_failures = 5  # Disconnect after 5 failed heartbeats（增加容忍度）
        
        while self.is_connected(session_id):
            try:
                await self.send_json(session_id, {"type": "heartbeat"})
                await asyncio.sleep(interval)
                
                # Reset failure counter on successful send
                consecutive_failures = 0
                
            except Exception as e:
                consecutive_failures += 1
                logger.warning(
                    f"Heartbeat failed for {session_id} "
                    f"({consecutive_failures}/{max_failures}): {e}"
                )
                
                if consecutive_failures >= max_failures:
                    logger.error(
                        f"Max heartbeat failures reached for {session_id}, "
                        "disconnecting"
                    )
                    break
                
                # Wait a bit before retry
                await asyncio.sleep(5)
        
        # Heartbeat loop ended, disconnect
        self.disconnect(session_id)
    
    def start_heartbeat(self, session_id: str, interval: int = 30):
        """Start heartbeat task for a connection"""
        if session_id not in self.connection_tasks:
            task = asyncio.create_task(self.heartbeat(session_id, interval))
            self.connection_tasks[session_id] = task
