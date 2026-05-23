"""Custom LLM provider for company's AI Farm platform."""

from __future__ import annotations

from typing import Any, List, Optional
from langchain.llms.base import LLM
from pydantic import Field
import requests
import json
from utils.logger import get_logger

logger = get_logger()


class AiFarmLLM(LLM):
    """
    Custom LLM for AI Farm platform (Azure-compatible API).
    
    Uses Bearer token authentication: Authorization: Bearer <api-key>
    Endpoint format: /api/openai/deployments/{deployment_id}/chat/completions?api-version=...
    """
    
    endpoint: str = Field(default="https://aoai-farm.bosch-temp.com", description="Base API endpoint URL")
    api_key: str = Field(default="", description="API key for Bearer token authentication")
    subscription_id: str = Field(default="", description="Subscription ID for tracking")
    deployment_id: str = Field(default="gpt-5-nano-2025-08-07", description="Deployment ID on AI Farm")
    api_version: str = Field(default="2025-04-01-preview", description="API version")
    temperature: float = Field(default=0.0, description="Temperature for generation")
    timeout: int = Field(default=120, description="Request timeout in seconds (AI Farm may have ~35-40s server-side limit)")
    
    class Config:
        """Pydantic config"""
        arbitrary_types_allowed = True
    
    @property
    def _llm_type(self) -> str:
        """Return type of llm."""
        return "ai_farm_llm"
    
    def _call(
        self,
        prompt: str,
        stop: Optional[list] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> str:
        """
        Call the AI Farm LLM API.
        
        Args:
            prompt: The prompt text
            stop: Stop sequences (optional)
            run_manager: Callback manager (optional, can be ignored)
            **kwargs: Additional arguments
            
        Returns:
            Generated text response
        """
        logger.info(
            "AiFarmLLM._call invoked: deployment=%s endpoint=%s",
            self.deployment_id,
            self.endpoint,
        )
        
        try:
            # Build headers with Bearer token authentication
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            
            payload = {
                "model": self.deployment_id,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "max_completion_tokens": 4096,
            }
            
            # NOTE: AI Farm API does not support 'stop' parameter, so we ignore it
            # even though LangChain may pass it
            
            # Build API URL with deployment ID and API version
            api_url = f"{self.endpoint.rstrip('/')}/api/openai/deployments/{self.deployment_id}/chat/completions?api-version={self.api_version}"
            logger.debug("Calling API: %s", api_url)
            
            # Make request
            response = requests.post(
                api_url,
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )
            
            response.raise_for_status()
            
            # Parse response
            response_data = response.json()
            logger.debug("API response status=%s", response.status_code)
            
            # Handle different response formats
            if "choices" in response_data and len(response_data["choices"]) > 0:
                choice = response_data["choices"][0]
                if "message" in choice:
                    content = choice["message"].get("content", "")
                    logger.info("AiFarmLLM successfully generated %d chars", len(content))
                    return content
                elif "text" in choice:
                    content = choice["text"]
                    logger.info("AiFarmLLM successfully generated %d chars", len(content))
                    return content
            
            error_msg = f"Unexpected response format: {response_data}"
            logger.error("AiFarmLLM error: %s", error_msg)
            raise ValueError(error_msg)
            
        except requests.exceptions.Timeout:
            error_msg = f"AI Farm API timeout after {self.timeout}s"
            logger.error("AiFarmLLM timeout: %s", error_msg)
            raise RuntimeError(error_msg)
        except requests.exceptions.ConnectionError as e:
            error_msg = f"AI Farm API connection failed: {str(e)}"
            logger.error("AiFarmLLM connection error: %s", error_msg)
            raise RuntimeError(error_msg)
        except requests.exceptions.HTTPError as e:
            error_msg = f"AI Farm API HTTP error {e.response.status_code}: {e.response.text}"
            logger.error("AiFarmLLM HTTP error: %s", error_msg)
            raise RuntimeError(error_msg)
        except requests.exceptions.RequestException as e:
            error_msg = f"AI Farm API request failed: {str(e)}"
            logger.error("AiFarmLLM request error: %s", error_msg)
            raise RuntimeError(error_msg)
        except (KeyError, ValueError, json.JSONDecodeError) as e:
            error_msg = f"Failed to parse AI Farm API response: {str(e)}"
            logger.error("AiFarmLLM parse error: %s", error_msg)
            raise RuntimeError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error in AiFarmLLM: {type(e).__name__}: {str(e)}"
            logger.error("AiFarmLLM unexpected error: %s", error_msg)
            raise RuntimeError(error_msg)
    
    def bind_tools(
        self,
        tools: List[Any],
        **kwargs: Any,
    ) -> AiFarmLLM:
        """
        Bind tools to this LLM instance.
        
        Since we're not using tools in this implementation,
        we simply return self. This method is required by LangChain's
        create_tool_calling_agent but our use case doesn't require tool binding.
        
        Args:
            tools: List of tools to bind (ignored)
            **kwargs: Additional arguments (ignored)
            
        Returns:
            Self (unchanged)
        """
        logger.debug("bind_tools() called with %d tools", len(tools))
        return self

