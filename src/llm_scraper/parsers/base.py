from __future__ import annotations

from typing import Any, Dict, List, Optional, Union
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from lxml import etree, html as lxml_html

from ..models.meta import ResponseMeta
from ..models.selector import ElementSelector, ParserConfig, SelectorType


class BaseParser:
    """
    A flexible HTML parser that uses a declarative configuration (`ParserConfig`)
    to extract structured data from HTML using both CSS selectors and XPath expressions.
    """

    def __init__(self, soup: BeautifulSoup, config: ParserConfig, base_url: Optional[str] = None):
        if not isinstance(soup, BeautifulSoup):
            raise TypeError("`soup` must be a BeautifulSoup instance.")
        if not isinstance(config, ParserConfig):
            raise TypeError("`config` must be a ParserConfig instance.")

        self.soup = soup
        self.config = config
        self.base_url = base_url
        
        # Create lxml tree for XPath support
        # Convert BeautifulSoup to string and parse with lxml for XPath
        try:
            html_string = str(soup)
            self.tree = lxml_html.fromstring(html_string)
        except Exception as e:
            print(f"Warning: Failed to create lxml tree for XPath support: {e}")
            self.tree = None
        
        self._run_cleanup()

    def _run_cleanup(self):
        """Remove unwanted elements from the soup before parsing (global cleanup)."""
        if not self.config.cleanup:
            return
        for selector in self.config.cleanup:
            try:
                # Detect selector type
                sel_type = self._detect_selector_type(selector, SelectorType.AUTO)
                
                if sel_type == SelectorType.CSS:
                    # CSS cleanup using BeautifulSoup
                    for tag in self.soup.select(selector):
                        tag.decompose()
                else:
                    # XPath cleanup using lxml tree
                    if self.tree is not None:
                        for element in self.tree.xpath(selector):
                            parent = element.getparent()
                            if parent is not None:
                                parent.remove(element)
                        # Update soup from modified tree
                        html_string = etree.tostring(self.tree, encoding='unicode', method='html')
                        self.soup = BeautifulSoup(html_string, 'lxml')
            except Exception as e:
                # Ignore errors during cleanup but log warning
                print(f"Warning: Failed to apply global cleanup selector '{selector}': {e}")
                pass

    @staticmethod
    def _detect_selector_type(query: str, explicit_type: SelectorType = SelectorType.AUTO) -> SelectorType:
        """
        Detect whether a query is CSS or XPath based on its syntax.
        
        Args:
            query: The selector query string
            explicit_type: Explicitly specified type (AUTO, CSS, or XPATH)
            
        Returns:
            SelectorType.CSS or SelectorType.XPATH
        """
        if explicit_type != SelectorType.AUTO:
            return explicit_type
        
        # Auto-detect: XPath starts with / or //
        if query.strip().startswith(('//', '/')):
            return SelectorType.XPATH
        
        return SelectorType.CSS
    
    def _extract_with_css(
        self, 
        query: str, 
        parent_element=None, 
        find_all: bool = False
    ) -> List[Any]:
        """
        Extract elements using CSS selector.
        
        Args:
            query: CSS selector string
            parent_element: Parent BeautifulSoup element to search within
            find_all: Whether to find all matches or just first
            
        Returns:
            List of BeautifulSoup elements
        """
        scope = parent_element if parent_element is not None else self.soup
        
        if find_all:
            return scope.select(query)
        else:
            element = scope.select_one(query)
            return [element] if element else []
    
    def _extract_with_xpath(
        self, 
        query: str, 
        parent_element=None, 
        find_all: bool = False
    ) -> List[Any]:
        """
        Extract elements using XPath expression.
        
        Args:
            query: XPath expression string
            parent_element: Parent lxml element to search within
            find_all: Whether to find all matches or just first
            
        Returns:
            List of lxml elements
        """
        if self.tree is None:
            return []
        
        try:
            scope = parent_element if parent_element is not None else self.tree
            
            # Execute XPath query
            results = scope.xpath(query)
            
            # Handle different result types
            if not results:
                return []
            
            # Filter to only element nodes
            elements = [r for r in results if isinstance(r, (etree._Element, lxml_html.HtmlElement))]
            
            if not find_all and elements:
                return [elements[0]]
            
            return elements
        except Exception as e:
            print(f"Warning: XPath query failed '{query}': {e}")
            return []
    
    def _find_parent_element(self, parent_query: str, selector_type: SelectorType):
        """
        Find parent element using CSS or XPath.
        
        Args:
            parent_query: Parent selector/XPath query
            selector_type: Type of selector (CSS or XPATH)
            
        Returns:
            Parent element (BeautifulSoup or lxml) or None
        """
        detected_type = self._detect_selector_type(parent_query, selector_type)
        
        if detected_type == SelectorType.CSS:
            return self.soup.select_one(parent_query)
        else:  # XPath
            if self.tree is None:
                return None
            results = self._extract_with_xpath(parent_query, find_all=False)
            return results[0] if results else None
    
    def _extract_value_from_element(
        self, 
        element: Any, 
        attribute: Optional[str], 
        extract_type: str,
        is_lxml: bool = False
    ) -> Optional[str]:
        """
        Extract value from an element (text, HTML, or attribute).
        
        Args:
            element: BeautifulSoup or lxml element
            attribute: Attribute name to extract
            extract_type: Type of extraction ('text', 'html', 'attribute')
            is_lxml: Whether element is lxml (True) or BeautifulSoup (False)
            
        Returns:
            Extracted string value or None
        """
        try:
            if attribute:
                # Extract specific attribute
                if is_lxml:
                    attr_val = element.get(attribute)
                else:
                    attr_val = element.get(attribute)
                    
                if attr_val:
                    # Convert relative URLs to absolute for href attributes
                    if attribute == 'href' and self.base_url:
                        attr_val = urljoin(self.base_url, attr_val)
                    return str(attr_val)
                    
            elif extract_type == "html":
                if is_lxml:
                    return etree.tostring(element, encoding='unicode', method='html')
                else:
                    return str(element)
                    
            else:  # text
                if is_lxml:
                    # Get text content from lxml element
                    return element.text_content().strip()
                else:
                    return element.get_text(strip=True)
                    
        except Exception as e:
            print(f"Warning: Failed to extract value from element: {e}")
            
        return None

    def _extract_element(self, selector: ElementSelector) -> Optional[Union[str, List[str]]]:
        """
        Core extraction logic. Finds element(s) based on the selector
        and extracts the specified data (text, html, or attribute).
        
        Supports both CSS selectors and XPath expressions with fallback chains:
        - Simple selector: "div.content" or "//div[@class='content']"
        - Array of selectors: ["div.content", "//article", "main"]
        - Array of selector configs: [
            {"query": "time", "selector_type": "css", "attribute": "datetime"},
            {"query": "//time[@pubdate]", "selector_type": "xpath"},
            ...
          ]
        """
        if not selector or not selector.selector:
            return None

        # Normalize selector to list of items
        selectors_list = selector.selector if isinstance(selector.selector, list) else [selector.selector]
        
        elements = []
        for sel_item in selectors_list:
            # Parse selector item
            if isinstance(sel_item, dict):
                # Selector config object: {"query": "time", "selector_type": "css", "attribute": "datetime", "parent": ".meta"}
                sel_query = sel_item.get("query")
                sel_type = SelectorType(sel_item.get("selector_type", "auto"))
                sel_attribute = sel_item.get("attribute")
                sel_parent = sel_item.get("parent")
            elif isinstance(sel_item, str):
                # Simple string selector
                sel_query = sel_item
                sel_type = SelectorType.AUTO
                sel_attribute = None
                sel_parent = None
            else:
                continue
            
            if not sel_query:
                continue
            
            try:
                # Detect selector type
                detected_type = self._detect_selector_type(sel_query, sel_type)
                
                # Find parent element if specified
                parent_element = None
                if sel_parent:
                    parent_element = self._find_parent_element(sel_parent, detected_type)
                    if parent_element is None:
                        continue  # Parent not found, try next selector
                
                # Extract elements based on type
                if detected_type == SelectorType.CSS:
                    found_elements = self._extract_with_css(sel_query, parent_element, selector.all)
                    is_lxml = False
                else:  # XPath
                    # For XPath with parent, we need to adjust the query
                    if parent_element is not None:
                        # If query doesn't start with ., make it relative
                        if not sel_query.startswith('.'):
                            sel_query = '.' + sel_query if sel_query.startswith('/') else './/' + sel_query
                    found_elements = self._extract_with_xpath(sel_query, parent_element, selector.all)
                    is_lxml = True
                
                if found_elements:
                    # Store elements with their specific attribute config and type info
                    for elem in found_elements:
                        elements.append((elem, sel_attribute, is_lxml))
                    
                    # Break after first successful selector (fallback chain logic)
                    # This applies whether all=True or all=False
                    break
                        
            except Exception as e:
                # Ignore invalid selectors
                print(f"Warning: Invalid selector '{sel_query}': {e}")
                continue
        
        if not elements:
            return None

        results = []
        for el, specific_attribute, is_lxml in elements:
            # Apply cleanup selectors if specified (per-field cleanup)
            if selector.cleanup:
                # Convert lxml element to BeautifulSoup for consistent cleanup
                if is_lxml:
                    from lxml import etree
                    html_str = etree.tostring(el, encoding='unicode', method='html')
                    el = BeautifulSoup(html_str, 'lxml')
                    # Get the first actual element (skip <html><body> wrappers)
                    el = el.find()
                    is_lxml = False
                
                # Apply cleanup selectors (support both CSS and XPath)
                for cleanup_sel in selector.cleanup:
                    try:
                        cleanup_type = self._detect_selector_type(cleanup_sel, SelectorType.AUTO)
                        
                        if cleanup_type == SelectorType.CSS:
                            # CSS cleanup using BeautifulSoup (simple and reliable)
                            for unwanted in el.select(cleanup_sel):
                                unwanted.decompose()
                        else:
                            # XPath cleanup - convert to lxml, clean, convert back
                            from lxml import html as lxml_html, etree
                            html_str = str(el)
                            tree = lxml_html.fromstring(html_str)
                            for unwanted in tree.xpath(cleanup_sel):
                                parent = unwanted.getparent()
                                if parent is not None:
                                    parent.remove(unwanted)
                            # Convert back to BeautifulSoup
                            html_str = etree.tostring(tree, encoding='unicode', method='html')
                            el = BeautifulSoup(html_str, 'lxml').find()
                    except Exception as e:
                        print(f"Warning: Failed to apply per-field cleanup selector '{cleanup_sel}': {e}")
            
            # Determine which attribute to use (specific > selector-level)
            attr_to_extract = specific_attribute or selector.attribute
            
            value = self._extract_value_from_element(
                el, 
                attr_to_extract, 
                selector.type,
                is_lxml
            )
            
            if value:
                results.append(value)

        if not results:
            return None

        return results if selector.all else results[0]

    def parse(self) -> Dict[str, Any]:
        """
        Executes all selectors in the config and returns a dictionary of parsed data.
        """
        parsed_data = {}
        # Iterate through the fields of the ParserConfig model (use class, not instance)
        for field in ParserConfig.model_fields:
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
