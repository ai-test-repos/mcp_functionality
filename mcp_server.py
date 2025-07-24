from mcp.server.fastmcp import FastMCP
import requests
import logging
mcp = FastMCP("Server", stateless_http=True)

# Constants
FALL_DETECT_URL = "http://localhost:8001"
VITAL_URL = "http://localhost:8080"

@mcp.tool(name="handle_fall_detection")
async def fall_detection() -> str:
    """
    Trying to test and log fall event
    """
    try:
        response = requests.post(f"{FALL_DETECT_URL}/detect_fall")
        response.raise_for_status()

        return f"Response from fall detection service: {response.json()}"


    except Exception as e:
        logging.error(f"Failed to log event: {e}")
        return f"Failed to log event: {str(e)}"

@mcp.tool(name="check_vitals")
async def check_vitals() -> str:
    """
    Trying to test and log fall event
    """
    try:
        response = requests.post(f"{VITAL_URL}/get_vitals")
        response.raise_for_status()

        return f"Response from vital service: {response.json()}"


    except Exception as e:
        logging.error(f"Failed to log event: {e}")
        return f"Failed to log event: {str(e)}"

if __name__ == "__main__":
    mcp.run(transport="streamable-http")