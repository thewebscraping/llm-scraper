from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

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

    def __init__(self, soup: BeautifulSoup, config: ParserConfig):
        if not isinstance(soup, BeautifulSoup):
            raise TypeError("`soup` must be a BeautifulSoup instance.")
        if not isinstance(config, ParserConfig):
            raise TypeError("`config` must be a ParserConfig instance.")

        self.soup = soup
        self.config = config
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
        If a list of selectors is provided, it tries them in order.
        """
        if not selector or not selector.css_selector:
            return None

        selectors = selector.css_selector if isinstance(selector.css_selector, list) else [selector.css_selector]
        
        elements = []
        for sel in selectors:
            try:
                if selector.all:
                    found_elements = self.soup.select(sel)
                    if found_elements:
                        elements.extend(found_elements)
                else:
                    element = self.soup.select_one(sel)
                    if element:
                        elements = [element]
                        break  # Found one, stop searching
            except Exception as e:
                # Ignore invalid selectors, but maybe log them
                print(f"Warning: Invalid selector '{sel}': {e}")
                continue
        
        if not elements:
            return None

        results = []
        for el in elements:
            try:
                if selector.type == "text":
                    results.append(el.get_text(strip=True))
                elif selector.type == "html":
                    results.append(str(el))
                elif selector.type == "attribute":
                    attr_val = el.get(selector.attribute)
                    if attr_val:
                        results.append(str(attr_val))
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


def get_parsed_data(html: str, config: ParserConfig) -> Dict[str, Any]:
    """
    High-level function to take raw HTML and a parser config,
    and return structured, parsed data.
    """
    soup = BeautifulSoup(html, "lxml")
    parser = BaseParser(soup, config)
    return parser.parse()


def get_metadata(html: str) -> ResponseMeta:
    """
    Extracts metadata (OpenGraph, Schema.org, etc.) from the HTML.
    """
    soup = BeautifulSoup(html, "lxml")
    meta_helper = ResponseMeta.from_soup(soup)

    schema_scripts = soup.find_all("script", type="application/ld+json")
    # A more robust implementation would merge multiple schemas
    if schema_scripts:
        try:
            # Use the first valid schema found
            for script in schema_scripts:
                if not script.string:
                    continue
                schema_ld = SchemaJsonLD.from_string(script.string)
                # Merge schema data into meta_helper, giving preference to existing values
                meta_dict = meta_helper.model_dump(exclude_unset=True)
                schema_dict = schema_ld.to_response_meta().model_dump(exclude_unset=True)
                
                # Schema data is used as a fallback
                for key, value in schema_dict.items():
                    if key not in meta_dict or meta_dict[key] is None:
                        meta_dict[key] = value
                
                return ResponseMeta.model_validate(meta_dict)

        except (ValidationError, IndexError, TypeError) as e:
            # Log error if schema parsing fails
            print(f"Could not parse Schema.org LD+JSON: {e}")

    return meta_helper