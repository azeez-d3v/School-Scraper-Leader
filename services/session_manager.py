import asyncio
from typing import Dict, List, Any, Optional, Union
from curl_cffi import AsyncSession

class SessionManager:
    """
    Session manager for making asynchronous HTTP requests using curl_cffi.
    """
    
    def __init__(self, default_headers: Optional[Dict[str, str]] = None):
        """
        Initialize the session manager.
        
        Args:
            default_headers: Default headers to use for all requests.
        """
        self.default_headers = default_headers or {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }
        
    async def make_requests(self, 
                           requests: List[Dict[str, Any]]) -> List[Any]:
        """
        Make multiple requests concurrently.
        
        Args:
            requests: List of request configurations, each containing:
                - url: The URL to request
                - method: HTTP method (default: 'GET')
                - headers: Optional headers (combined with default_headers)
                - data: Optional request payload
                - json: Optional JSON payload (will be serialized)
                
        Returns:
            List of response objects
        """
        async with AsyncSession(impersonate="chrome131") as session:
            tasks = []
            for req in requests:
                url = req['url']
                method = req.get('method', 'GET').lower()
                
                # Combine default headers with request-specific headers
                headers = {**self.default_headers}
                if 'headers' in req:
                    headers.update(req['headers'])
                
                # Build request kwargs
                kwargs = {'headers': headers}
                
                if 'data' in req:
                    kwargs['data'] = req['data']
                    
                if 'json' in req:
                    kwargs['json'] = req['json']
                
                # Create appropriate request task based on method
                http_method = getattr(session, method)
                task = http_method(url, **kwargs)
                tasks.append(task)
                
            return await asyncio.gather(*tasks, return_exceptions=True)
    
    async def get(self, url: str, headers: Optional[Dict[str, str]] = None) -> Any:
        """
        Make a GET request.
        
        Args:
            url: The URL to request
            headers: Optional headers
            
        Returns:
            Response object with html content
        """
        try:
            async with AsyncSession(impersonate="chrome131", timeout=(5.0, 120)) as session:
                combined_headers = {**self.default_headers}
                
                if headers:
                    combined_headers.update(headers)
                
                response = await session.get(url, headers=combined_headers)
                
                # Create a custom response object that has both text property and text() method
                # for compatibility with different access patterns
                class CustomResponse:
                    def __init__(self, original_response):
                        self.original = original_response
                        self.status_code = original_response.status_code
                        self._text = original_response.text
                    
                    def text(self):
                        return self._text
                    
                    @property
                    def text(self):
                        return self._text
                
                return CustomResponse(response)
                
        except Exception as e:
            # Create a more informative empty response
            class EmptyResponse:
                def __init__(self, error):
                    self.status_code = 500
                    self._text = f"Error fetching content: {str(error)}"
                    self.error = error
                
                def text(self):
                    return self._text
                
                @property
                def text(self):
                    return self._text
                    
            return EmptyResponse(e)
    
    async def post(self, url: str, 
                  data: Optional[Union[str, Dict]] = None,
                  json: Optional[Dict] = None,
                  headers: Optional[Dict[str, str]] = None) -> Any:
        """
        Make a POST request.
        
        Args:
            url: The URL to request
            data: Optional request payload
            json: Optional JSON payload
            headers: Optional headers
            
        Returns:
            Response object
        """
        try:
            async with AsyncSession(impersonate="chrome131") as session:
                combined_headers = {**self.default_headers}
                if headers:
                    combined_headers.update(headers)
                
                kwargs = {'headers': combined_headers}
                if data is not None:
                    kwargs['data'] = data
                if json is not None:
                    kwargs['json'] = json
                
                response = await session.post(url, **kwargs)
                
                # Create a custom response object that has both text property and text() method
                class CustomResponse:
                    def __init__(self, original_response):
                        self.original = original_response
                        self.status_code = original_response.status_code
                        self._text = original_response.text
                    
                    def text(self):
                        return self._text
                    
                    @property
                    def text(self):
                        return self._text
                
                return CustomResponse(response)
                
        except Exception as e:
            # Create a more informative empty response
            class EmptyResponse:
                def __init__(self, error):
                    self.status_code = 500
                    self._text = f"Error fetching content: {str(error)}"
                    self.error = error
                
                def text(self):
                    return self._text
                
                @property
                def text(self):
                    return self._text
                    
            return EmptyResponse(e)