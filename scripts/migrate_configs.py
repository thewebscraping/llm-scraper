#!/usr/bin/env python3
"""
Migrate all parser configs to new architecture:
1. Remove deprecated "type" field from ElementSelector
2. Add global "cleanup" at top level (script, style, noscript, iframe)
3. Move cleanup to content.cleanup for per-field cleanup
4. Ensure proper structure for Pydantic v2
"""
import json
from pathlib import Path


def migrate_config(config_path: Path) -> bool:
    """
    Migrate a single config file to new architecture.
    
    Returns:
        True if file was modified, False otherwise
    """
    try:
        # Read config
        config = json.loads(config_path.read_text(encoding='utf-8'))
        modified = False
        
        # 1. Add global cleanup if not exists
        if "cleanup" not in config:
            config["cleanup"] = ["script", "style", "noscript", "iframe"]
            modified = True
        elif config["cleanup"] and "script" not in config["cleanup"]:
            # Ensure global cleanup has base items
            base_cleanup = ["script", "style", "noscript", "iframe"]
            existing = config["cleanup"]
            config["cleanup"] = base_cleanup + [c for c in existing if c not in base_cleanup]
            modified = True
        
        # 2. Process all field selectors
        for field in ["title", "description", "content", "authors", "date_published", 
                      "date_modified", "tags", "topics", "follow_urls", "main_points"]:
            if field in config and isinstance(config[field], dict):
                field_config = config[field]
                
                # Rename "css_selector" to "selector"
                if "css_selector" in field_config:
                    field_config["selector"] = field_config.pop("css_selector")
                    modified = True
                
                # Remove "type" field (deprecated in Pydantic v2)
                if "type" in field_config:
                    del field_config["type"]
                    modified = True
        
        # 3. Move global cleanup items to content.cleanup if needed
        if "content" in config and isinstance(config["content"], dict):
            content = config["content"]
            
            # Get current content cleanup
            content_cleanup = content.get("cleanup", [])
            
            # Remove script/style/noscript/iframe from content.cleanup (now in global)
            base_items = ["script", "style", "noscript", "iframe"]
            if content_cleanup:
                # Filter out base items
                filtered = [c for c in content_cleanup if c not in base_items]
                if len(filtered) != len(content_cleanup):
                    content["cleanup"] = filtered if filtered else None
                    if content["cleanup"] is None:
                        del content["cleanup"]
                    modified = True
            
            # If no cleanup specified, add common ones
            if "cleanup" not in content or not content.get("cleanup"):
                content["cleanup"] = [
                    ".ads",
                    ".advertisement",
                    ".related-posts",
                    ".newsletter",
                    ".social-share",
                    "[class*='sponsor']",
                    "[class*='promoted']"
                ]
                modified = True
        
        # 4. Write back if modified
        if modified:
            config_path.write_text(
                json.dumps(config, indent=2, ensure_ascii=False) + "\n",
                encoding='utf-8'
            )
            return True
        
        return False
        
    except Exception as e:
        print(f"❌ Error processing {config_path}: {e}")
        return False


def main():
    """Migrate all config files."""
    configs_dir = Path("src/llm_scraper/parsers/configs")
    
    if not configs_dir.exists():
        print(f"❌ Config directory not found: {configs_dir}")
        return 1
    
    # Find all JSON files
    config_files = list(configs_dir.rglob("*.json"))
    
    print(f"🔍 Found {len(config_files)} config files")
    print("=" * 60)
    
    modified_count = 0
    skipped_count = 0
    
    for config_path in sorted(config_files):
        relative_path = config_path.relative_to(configs_dir)
        
        if migrate_config(config_path):
            print(f"✅ Migrated: {relative_path}")
            modified_count += 1
        else:
            print(f"⏭️  Skipped:  {relative_path} (no changes needed)")
            skipped_count += 1
    
    print("\n" + "=" * 60)
    print("📊 Summary:")
    print(f"   Modified: {modified_count}")
    print(f"   Skipped:  {skipped_count}")
    print(f"   Total:    {len(config_files)}")
    print("\n✨ Migration complete!")
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
