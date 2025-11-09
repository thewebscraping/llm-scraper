from __future__ import annotations

from typing import Any, Dict, List, Optional, Union
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from pydantic import ValidationError

from ..models.meta import ResponseMeta
from ..models.schema import SchemaJsonLD
from ..models.selector import ElementSelector, ParserConfig


class BaseParser:
    """
    A flexible HTML parser that uses a declarative configuration (`ParserConfig`)
    to extract structured data from a BeautifulSoup object.
    """

    def __init__(self, soup: BeautifulSoup, config: ParserConfig, base_url: Optional[str] = None):
        if not isinstance(soup, BeautifulSoup):
            raise TypeError("`soup` must be a BeautifulSoup instance.")
        if not isinstance(config, ParserConfig):
            raise TypeError("`config` must be a ParserConfig instance.")

        self.soup = soup
        self.config = config
        self.base_url = base_url
        self._run_cleanup()

    def _run_cleanup(self):
        """Remove unwanted elements from the soup before parsing."""
        if not self.config.cleanup:
            return
        for selector in self.config.cleanup:
            try:
                for tag in self.soup.select(selector):
                    tag.decompose()
            except Exception:
                # Ignore errors during cleanup
                pass

    def _extract_element(self, selector: ElementSelector) -> Optional[Union[str, List[str]]]:
        """
        Core extraction logic. Finds element(s) based on the selector
        and extracts the specified data (text, html, or attribute).
        
        Supports:
        - Simple selector: "div.content"
        - Array of selectors: ["div.content", "article"]
        - Array of selector configs: [{"selector": "time", "attribute": "datetime"}, ...]
        """
        if not selector or not selector.css_selector:
            return None

        # Normalize css_selector to list of SelectorConfig objects
        selectors_list = selector.css_selector if isinstance(selector.css_selector, list) else [selector.css_selector]
        
        elements = []
        for sel_item in selectors_list:
            # Parse selector item
            if isinstance(sel_item, dict):
                # Selector config object: {"selector": "time", "attribute": "datetime", "parent": ".meta"}
                sel_str = sel_item.get("selector")
                sel_attribute = sel_item.get("attribute")
                sel_parent = sel_item.get("parent")
            elif isinstance(sel_item, str):
                # Simple string selector
                sel_str = sel_item
                sel_attribute = None
                sel_parent = None
            else:
                continue
            
            if not sel_str:
                continue
            
            try:
                # Find scope (parent or whole soup)
                scope = self.soup
                if sel_parent:
                    parent_element = self.soup.select_one(sel_parent)
                    if not parent_element:
                        continue  # Parent not found, try next selector
                    scope = parent_element
                
                # Find elements within scope
                if selector.all:
                    found_elements = scope.select(sel_str)
                    if found_elements:
                        # Store elements with their specific attribute config
                        for elem in found_elements:
                            elements.append((elem, sel_attribute))
                else:
                    element = scope.select_one(sel_str)
                    if element:
                        elements = [(element, sel_attribute)]
                        break  # Found one, stop searching
            except Exception as e:
                # Ignore invalid selectors
                print(f"Warning: Invalid selector '{sel_str}': {e}")
                continue
        
        if not elements:
            return None

        results = []
        for el, specific_attribute in elements:
            try:
                # Determine which attribute to use (specific > selector-level > type-based)
                attr_to_extract = specific_attribute or selector.attribute
                
                if attr_to_extract:
                    # Extract specific attribute
                    attr_val = el.get(attr_to_extract)
                    if attr_val:
                        # Convert relative URLs to absolute for href attributes
                        if attr_to_extract == 'href' and self.base_url:
                            attr_val = urljoin(self.base_url, attr_val)
                        results.append(str(attr_val))
                elif selector.type == "html":
                    results.append(str(el))
                else:  # Default to text extraction
                    results.append(el.get_text(strip=True))
            except Exception:
                # Ignore errors on a per-element basis
                continue

        if not results:
            return None

        return results if selector.all else results[0]

    def parse(self) -> Dict[str, Any]:
        """
        Executes all selectors in the config and returns a dictionary of parsed data.
        """
        parsed_data = {}
        # Iterate through the fields of the ParserConfig model
        for field in self.config.model_fields:
            if field == "cleanup":
                continue
            
            selector_data = getattr(self.config, field)
            if selector_data and isinstance(selector_data, ElementSelector):
                value = self._extract_element(selector_data)
                if value:
                    parsed_data[field] = value

        return parsed_data


def get_parsed_data(html: str, config: ParserConfig, base_url: Optional[str] = None) -> Dict[str, Any]:
    """
    High-level function to take raw HTML and a parser config,
    and return structured, parsed data.
    """
    soup = BeautifulSoup(html, "lxml")
    parser = BaseParser(soup, config, base_url)
    return parser.parse()


def get_metadata(html: str) -> ResponseMeta:
    """
    Extracts metadata (OpenGraph, Schema.org, etc.) from the HTML.
    """
    soup = BeautifulSoup(html, "lxml")
    meta_helper = ResponseMeta.from_soup(soup)

    # Extract topics from Schema.org BreadcrumbList and collect all schemas
    schema_topics = []
    all_schemas = []
    try:
        from ..models.schema import SchemaJsonLD, SchemaBreadcrumbList
        import json
        
        schema_scripts = soup.find_all("script", type="application/ld+json")
        for script in schema_scripts:
            try:
                # Parse raw JSON-LD
                raw_data = json.loads(script.string)
                all_schemas.append(raw_data)
                
                # Parse with SchemaJsonLD for structured extraction
                schema_data = SchemaJsonLD.parse(script.string)
                # Handle both single schema and list of schemas
                schemas = schema_data if isinstance(schema_data, list) else [schema_data]
                for schema in schemas:
                    if isinstance(schema, SchemaBreadcrumbList):
                        schema_topics.extend(schema.topics)
            except Exception:
                continue
    except Exception:
        pass
    
    # Add schema topics to meta if found
    if schema_topics and not meta_helper.topics:
        meta_helper.topics = schema_topics
    
    # Store all raw schemas if found
    if all_schemas:
        meta_helper.schema_org = all_schemas if len(all_schemas) > 1 else all_schemas[0]
    
    return meta_helper
