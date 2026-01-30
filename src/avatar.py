"""
Bitcoin Face Avatar Generation
==============================
Generate unique AI agent avatars using bitcoinfaces.xyz API.

Bitcoin Faces creates deterministic avatars from Bitcoin/Stacks addresses.
Free preview available, premium for high-res.
"""

import httpx
import hashlib
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class BitcoinFace:
    """Generated Bitcoin Face avatar."""
    address: str
    preview_url: str
    full_url: Optional[str]
    seed_hash: str


# Bitcoin Faces API endpoints
BITCOINFACES_API = "https://bitcoinfaces.xyz/api"
BITCOINFACES_CDN = "https://bitcoinfaces.xyz"


def generate_face_seed(address: str, salt: str = "") -> str:
    """
    Generate a deterministic seed for face generation.

    Args:
        address: STX or BTC address
        salt: Optional salt for variation

    Returns:
        Hex-encoded seed hash
    """
    data = f"{address}{salt}".encode()
    return hashlib.sha256(data).hexdigest()


async def get_face_preview(address: str) -> Optional[str]:
    """
    Get a preview URL for a Bitcoin Face.

    The preview is free and lower resolution.

    Args:
        address: STX or BTC address

    Returns:
        URL to preview image or None
    """
    # Bitcoin Faces generates faces based on address
    # The URL pattern is deterministic
    preview_url = f"{BITCOINFACES_CDN}/face/{address}?size=256"

    # Verify the URL works
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.head(preview_url, follow_redirects=True)
            if resp.status_code == 200:
                return preview_url
        except Exception:
            pass

    # Fallback to a generated identicon style
    return f"https://api.dicebear.com/7.x/identicon/svg?seed={address}"


async def generate_agent_avatar(
    address: str,
    agent_name: str,
    style: str = "bitcoin"
) -> BitcoinFace:
    """
    Generate a unique avatar for an AI agent.

    Args:
        address: Agent's STX address
        agent_name: Agent's name for additional uniqueness
        style: Avatar style ("bitcoin", "pixel", "abstract")

    Returns:
        BitcoinFace with URLs
    """
    # Generate seed from address + name
    seed = generate_face_seed(address, agent_name)

    # Get preview URL
    preview_url = await get_face_preview(address)

    # Full URL would require API key for high-res
    full_url = None

    return BitcoinFace(
        address=address,
        preview_url=preview_url or f"https://api.dicebear.com/7.x/bottts/svg?seed={seed}",
        full_url=full_url,
        seed_hash=seed
    )


async def get_alternative_avatars(address: str) -> Dict[str, str]:
    """
    Get multiple avatar style options.

    Returns:
        Dict mapping style names to URLs
    """
    seed = generate_face_seed(address)

    return {
        "identicon": f"https://api.dicebear.com/7.x/identicon/svg?seed={seed}",
        "bottts": f"https://api.dicebear.com/7.x/bottts/svg?seed={seed}",
        "shapes": f"https://api.dicebear.com/7.x/shapes/svg?seed={seed}",
        "pixel": f"https://api.dicebear.com/7.x/pixel-art/svg?seed={seed}",
        "bitcoin_face": f"{BITCOINFACES_CDN}/face/{address}?size=256",
    }


class AvatarManager:
    """
    Manage agent avatars with hosting support.

    Usage:
        manager = AvatarManager()
        avatar = await manager.create_avatar(address, "my-agent")
        hosted_url = await manager.host_avatar(avatar, "my-server.com")
    """

    def __init__(self, hosting_url: Optional[str] = None):
        """
        Initialize avatar manager.

        Args:
            hosting_url: Optional self-hosted URL for avatars
        """
        self.hosting_url = hosting_url

    async def create_avatar(
        self,
        address: str,
        agent_name: str
    ) -> BitcoinFace:
        """Create a new avatar for an agent."""
        return await generate_agent_avatar(address, agent_name)

    async def get_all_styles(self, address: str) -> Dict[str, str]:
        """Get all available avatar styles."""
        return await get_alternative_avatars(address)

    async def download_avatar(
        self,
        url: str,
        output_path: str
    ) -> bool:
        """
        Download an avatar to local file.

        Args:
            url: Avatar URL
            output_path: Local file path

        Returns:
            True if successful
        """
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(url, follow_redirects=True)
                if resp.status_code == 200:
                    with open(output_path, 'wb') as f:
                        f.write(resp.content)
                    return True
            except Exception as e:
                print(f"Failed to download avatar: {e}")
        return False

    def get_hosted_url(self, avatar: BitcoinFace) -> str:
        """
        Get the best available URL for an avatar.

        Prefers self-hosted if available, falls back to CDN.
        """
        if self.hosting_url:
            return f"{self.hosting_url}/avatars/{avatar.seed_hash}.png"
        return avatar.preview_url


# CLI helper
if __name__ == "__main__":
    import asyncio
    import sys

    async def main():
        address = sys.argv[1] if len(sys.argv) > 1 else "SP3N0NQ47ABAZV68PQSJY7V2H4F2J709ATTESYBRD"

        print(f"Generating avatar for: {address}\n")

        manager = AvatarManager()
        avatar = await manager.create_avatar(address, "test-agent")

        print(f"Preview URL: {avatar.preview_url}")
        print(f"Seed Hash:   {avatar.seed_hash}")

        print("\nAll styles:")
        styles = await manager.get_all_styles(address)
        for name, url in styles.items():
            print(f"  {name}: {url}")

    asyncio.run(main())
