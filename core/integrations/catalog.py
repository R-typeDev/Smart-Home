PLATFORM_CATALOG = [
    {
        "id": "tplink",
        "name_key": "integrations.tplinkPlatform",
        "description_key": "integrations.tplinkPlatformDescription",
        "logo": "/pages/integrations/modules/tplink/logo.svg",
        "route": "/integrations#tplink",
        "methods": [
            {
                "id": "tplink_local",
                "name_key": "integrations.tplinkRouter",
                "description_key": "integrations.tplinkRouterDescription",
                "connection_type": "local",
                "icon": "network",
                "route": "/integrations#tplink/router",
            },
        ],
    },
    {
        "id": "tuya",
        "name_key": "integrations.tuya",
        "description_key": "integrations.tuyaDescription",
        "logo": "/pages/integrations/modules/tuya/logo.png",
        "route": "/integrations#tuya",
        "methods": [
            {
                "id": "tuya_cloud",
                "name_key": "integrations.tuyaCloud",
                "description_key": "integrations.cloudDescription",
                "connection_type": "cloud",
                "icon": "cloud",
                "route": "/integrations#tuya/cloud",
            },
            {
                "id": "tuya_local",
                "name_key": "integrations.tuyaLocal",
                "description_key": "integrations.localDescription",
                "connection_type": "local",
                "icon": "network",
                "route": "/integrations#tuya/local",
            },
        ],
    },
]
