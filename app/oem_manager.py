"""
OEM Configuration Manager for Flask Application
Handles branding and customization settings from config.yaml
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class OEMConfig:
    """OEM configuration management class"""
    
    # Default configuration
    DEFAULT_CONFIG = {
        'branding': {
            'user_title': 'EzySpeech User',
            'admin_title': 'EzySpeech Admin',
            'login_title': 'EzySpeech Admin',
            'app_name': 'EzySpeech'
        },
        'assets': {
            'brand_icon': '🎙️',
            'favicon': '',
            'login_icon': '🎙️'
        },
        'advanced': {
            'mobile_show_title': True,
            'icon_scale': 1.0
        }
    }
    
    def __init__(self, enabled: bool = True, config_data: Optional[Dict[str, Any]] = None):
        """
        Initialize OEM configuration from config.yaml data
        
        Args:
            enabled: Whether OEM customization is enabled
            config_data: OEM configuration dictionary from config.yaml
        """
        self.enabled = enabled
        self.config = self._load_config(config_data)
    
    def _load_config(self, config_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Load OEM configuration
        
        Args:
            config_data: OEM configuration from config.yaml
        
        Returns:
            Configuration dictionary
        """
        # Start with defaults
        config = self.DEFAULT_CONFIG.copy()
        
        # If OEM is disabled, return default config
        if not self.enabled:
            logger.info("OEM customization is disabled in config.yaml")
            return config
        
        # Merge with provided config data
        if config_data:
            config = self._deep_merge(config, config_data)
            logger.info("✓ OEM configuration loaded from config.yaml")
        
        return config
    
    @staticmethod
    def _deep_merge(base: Dict, updates: Dict) -> Dict:
        """
        Deep merge two dictionaries
        
        Args:
            base: Base dictionary
            updates: Update dictionary
        
        Returns:
            Merged dictionary
        """
        result = base.copy()
        for key, value in updates.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = OEMConfig._deep_merge(result[key], value)
            else:
                result[key] = value
        return result
    
    def get_branding(self) -> Dict[str, str]:
        """Get branding information"""
        return self.config.get('branding', self.DEFAULT_CONFIG['branding'])
    
    def get_assets(self) -> Dict[str, str]:
        """Get asset information"""
        return self.config.get('assets', self.DEFAULT_CONFIG['assets'])
    
    def get_advanced(self) -> Dict[str, Any]:
        """Get advanced settings"""
        return self.config.get('advanced', self.DEFAULT_CONFIG['advanced'])
    
    def get_user_title(self) -> str:
        """Get user interface title"""
        return self.get_branding().get('user_title', self.DEFAULT_CONFIG['branding']['user_title'])
    
    def get_admin_title(self) -> str:
        """Get admin interface title"""
        return self.get_branding().get('admin_title', self.DEFAULT_CONFIG['branding']['admin_title'])
    
    def get_login_title(self) -> str:
        """Get login page title"""
        return self.get_branding().get('login_title', self.DEFAULT_CONFIG['branding']['login_title'])
    
    def get_app_name(self) -> str:
        """Get application name"""
        return self.get_branding().get('app_name', self.DEFAULT_CONFIG['branding']['app_name'])
    
    def get_brand_icon(self) -> str:
        """Get brand icon"""
        return self.get_assets().get('brand_icon', self.DEFAULT_CONFIG['assets']['brand_icon'])
    
    def get_favicon(self) -> str:
        """Get favicon path"""
        return self.get_assets().get('favicon', '')
    
    def get_login_icon(self) -> str:
        """Get login page icon"""
        return self.get_assets().get('login_icon', self.DEFAULT_CONFIG['assets']['login_icon'])
    
    def get_mobile_show_title(self) -> bool:
        """Get whether to show full title on mobile devices"""
        return self.get_advanced().get('mobile_show_title', True)
    
    def get_icon_scale(self) -> float:
        """Get icon scale multiplier"""
        return self.get_advanced().get('icon_scale', 1.0)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Get complete configuration dictionary
        
        Returns:
            Configuration dictionary
        """
        return self.config
    
    def to_json_safe(self) -> Dict[str, Any]:
        """
        Get JSON-serializable configuration (for frontend)
        
        Returns:
            Configuration dictionary
        """
        config = self.to_dict()
        return {
            'branding': config.get('branding', {}),
            'assets': config.get('assets', {}),
            'advanced': config.get('advanced', {})
        }


def init_oem_config(app, get_config_func):
    """
    Initialize OEM configuration for Flask application
    
    Args:
        app: Flask application instance
        get_config_func: Function to get config values - get_config(*keys, default=None)
    
    Returns:
        OEMConfig instance
    """
    # Get OEM settings from main config
    oem_enabled = get_config_func('oem', 'enabled', default=True)
    
    # Extract OEM configuration section
    oem_config_data = {
        'branding': get_config_func('oem', 'branding', default={}),
        'assets': get_config_func('oem', 'assets', default={}),
        'advanced': get_config_func('oem', 'advanced', default={})
    }
    
    # Create OEM config instance
    oem_config = OEMConfig(enabled=oem_enabled, config_data=oem_config_data)
    
    # Inject OEM configuration into app.config
    app.config['OEM'] = oem_config.to_json_safe()
    
    # Create template global variables
    app.jinja_env.globals.update(
        oem_user_title=oem_config.get_user_title(),
        oem_admin_title=oem_config.get_admin_title(),
        oem_login_title=oem_config.get_login_title(),
        oem_app_name=oem_config.get_app_name(),
        oem_brand_icon=oem_config.get_brand_icon(),
        oem_favicon=oem_config.get_favicon(),
        oem_login_icon=oem_config.get_login_icon(),
        oem_mobile_show_title=oem_config.get_mobile_show_title(),
        oem_icon_scale=oem_config.get_icon_scale()
    )
    
    status = "enabled" if oem_enabled else "disabled"
    logger.info(f"✓ OEM Configuration initialized (status: {status})")
    
    return oem_config
