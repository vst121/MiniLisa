"""ClamAV daemon (clamd) scanner adapter.

Talks to a running `clamd` over TCP using the INSTREAM protocol. This is the
standard, dependency-free way to integrate ClamAV without binding to a
specific Python client package. The scanner is fail-closed: any transport or
scan error is reported as a rejected file so malware can never slip through
because the scanner was unavailable.
"""

import asyncio
import logging
import struct

from src.auth.security import VirusScanner

logger = logging.getLogger(__name__)

# INSTREAM chunk header is a 4-byte big-endian length prefix.
_CHUNK_HEADER = struct.Struct(">I")


class ClamAVScanner(VirusScanner):
    """Production ClamAV scanner backed by a clamd TCP endpoint."""

    def __init__(self, host: str, port: int, timeout: float = 10.0) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout

    async def scan_bytes(self, content: bytes, filename: str) -> tuple[bool, str]:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=self.timeout,
            )
        except (OSError, asyncio.TimeoutError) as exc:
            logger.error(
                "[ClamAV] Cannot reach clamd at %s:%s: %s", self.host, self.port, exc
            )
            return False, f"scanner unavailable ({exc})"

        try:
            writer.write(b"INSTREAM\r\n")
            # Send content in 64 KiB chunks to respect clamd buffer limits.
            for offset in range(0, len(content), 64 * 1024):
                chunk = content[offset : offset + 64 * 1024]
                writer.write(_CHUNK_HEADER.pack(len(chunk)))
                writer.write(chunk)
            # Zero-length chunk terminates the stream.
            writer.write(_CHUNK_HEADER.pack(0))
            await writer.drain()

            response = await asyncio.wait_for(reader.read(4096), timeout=self.timeout)
        except (OSError, asyncio.TimeoutError) as exc:
            logger.error("[ClamAV] Scan failed for %s: %s", filename, exc)
            return False, f"scanner error ({exc})"
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

        text = response.decode("utf-8", errors="replace").strip()
        if text.startswith("stream:") and ": OK" in text:
            return True, "CLEAN"
        if "FOUND" in text:
            # ClamAV format: "stream: <path>: <signature> FOUND"
            before_found = text.split("FOUND", 1)[0]
            signature = before_found.rsplit(":", 1)[-1].strip()
            logger.warning("[ClamAV] MALWARE DETECTED in %s: %s", filename, signature)
            return False, signature or "Win32.Malware.UNKNOWN"
        logger.error("[ClamAV] Unexpected response for %s: %s", filename, text)
        return False, f"scanner error (unexpected response: {text})"