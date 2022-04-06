#!/usr/bin/env python3
"""
    This script provides OpenHab codegen functionality.
    Purpose: generate repeating items config.

    Plug - have only ON/OFF states
"""

import os
import logging
import argparse
import numpy as np
import yaml
from pprint import pp

from codegen.devices import DEVICES

logging.basicConfig(level=logging.DEBUG)

ROOT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
PREAMBULA = """
// ==========================================
// THIS FILE IS AUTO GENERATED
// Do not edit by hands
// Use this command to regenerate:
// python3 ./bin/codegen.py
// ==========================================

"""

# Items defentition
items = [
    # Room 1
    {
        'name': "R1 Climate",
        'id': "r1_climate",
        'zigbee_id': '0xa4c138f5460e22dd',
        'type': DEVICES.TUYA_TEMPERATURE_SENSOR_TS0201,
    },
    {
        'name': "R1 Table",
        'id': "r1_table",
        'zigbee_id': '0x7cb03eaa0a09e7bc',
        'type': DEVICES.OSRAM_SMART_PLUG,
    },
    {
        'name': "Exit button",
        'id': "exit_button",
        'zigbee_id': '0x04cd15fffe6d57dc',
        'type': DEVICES.IKEA_TRADFRI_STYRBAR,
    },
    # Kitchen
    {
        'name': "KU Climate",
        'id': "ku_climate",
        'zigbee_id': '0xa4c1386df39045f6',
        'type': DEVICES.TUYA_TEMPERATURE_SENSOR_TS0201,
    },
]


def device_label(item):
    device_id = ''
    if np.in1d(['zigbee'], item['type']['types']).any():
        device_id = item['zigbee_id']
    else:
        device_id = item['id']
    return f"{item['name']} ({device_id})"


def device_comment(item):
    conf_str = []
    conf_str.append(f"// {device_label(item)}")
    conf_str.append(
        f"// {item['type']['device_name']}"
        f" / {item['type']['device_url']}"
    )
    return conf_str


def device_groups(item, typ):
    if 'groups' in item and typ in item['groups']:
        return ' (' + ','.join(item['groups'][typ])+')'
    return ''


def device_short_id(id):
    return id[-4:]


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Openhab codegen')

    parser.add_argument(
        '--write', action='store_true', help='Write config files to FS')

    args = parser.parse_args()

    logging.info(f"Processing {len(items)} devices")

    # Generate some common values
    item_ids = []
    zigbee_ids = []
    zigbee_devices_list = {}
    for x, item in enumerate(items):
        if item['id'] in item_ids:
            raise Exception(f"Device ID {item['id']} is not unique!")
        item_ids.append(item['id'])
        items[x]['mqtt_topic'] = f"{items[x]['id']}"
        if np.in1d(['zigbee'], item['type']['types']).any():
            # Add to all Zigbee items generated MQTT topic like "zigbee-XXXX"
            items[x]['zigbee_short'] = device_short_id(item['zigbee_id'])
            # Add ids to check conflicts
            if items[x]['zigbee_short'] in zigbee_ids:
                raise Exception(f"Device ID {item['id']} is not unique!")
            zigbee_ids.append(items[x]['zigbee_short'])
            zigbee_devices_list[item['zigbee_id']] = item['id']

    # Generate THINGS
    conf_str = [PREAMBULA]
    for item in items:
        # tasmota-wifi device?
        if 'tasmota' in item['type']['types']:
            conf_str.extend(device_comment(item))
            conf_str.append(
                f"Thing mqtt:topic:openhab:{item['mqtt_topic']} \"{item['name']}\" (mqtt:broker:openhab) {{")
            conf_str.append(
                f"\tChannels:")

            # Iterate through avaliable channels
            for channel in item['type']['tasmota_channels']:
                command_opts = ''
                if 'switch' == channel['type']:
                    command_opts = ", on=\"ON\", off=\"OFF\""
                if 'dimmer' == channel['type']:
                    command_opts = ", min=1, max=100"
                conf_str.append(
                    f"\t\tType {channel['type']} : {channel['id']} ["
                    f"stateTopic=\"stat/{item['id']}/RESULT\""
                    f", transformationPattern=\"JSONPATH:$.{channel['id']}\""
                    f", commandTopic=\"cmnd/{item['id']}/{channel['id']}\""
                    f"{command_opts}"
                    f"]"
                )

            # Standard signal values
            conf_str.append(
                f"\t\tType number : rssi ["
                f"stateTopic=\"tele/{item['id']}/STATE\""
                f", transformationPattern=\"JSONPATH:$.Wifi.RSSI\""
                f"]"
            )
            conf_str.append(
                f"\t\tType string : bssid ["
                f"stateTopic=\"tele/{item['id']}/STATE\""
                f", transformationPattern=\"JSONPATH:$.Wifi.BSSId\""
                f"]"
            )
            conf_str.append(
                f"\t\tType number : la ["
                f"stateTopic=\"tele/{item['id']}/STATE\""
                f", transformationPattern=\"JSONPATH:$.LoadAvg\""
                f"]"
            )

            # Some wifi devices needs to be monitored
            if np.in1d(['activity'], item['type']['types']).any():
                conf_str.append(
                    f"\t\tType datetime : activity [stateTopic=\"tele/{item['id']}/STATE\", transformationPattern=\"JS:z2m-activity.js\"]")

            conf_str.append(f"}}")

        # Zigbee2mqtt device?
        if 'zigbee' in item['type']['types']:
            conf_str.extend(device_comment(item))
            conf_str.append(
                f"Thing mqtt:topic:openhab:{item['mqtt_topic']} \"{item['name']}\" (mqtt:broker:openhab) {{")
            conf_str.append(
                f"\tChannels:")
            zigbe_mqtt_topic = f"zigbee2mqtt/{item['id']}"
            # Device has switch option
            if np.in1d(['lamp', 'plug'], item['type']['types']).any():
                conf_str.append(
                    f"\t\tType switch : state ["
                    f"stateTopic=\"{zigbe_mqtt_topic}\""
                    f", transformationPattern=\"JSONPATH:$.state\""
                    f", commandTopic=\"{zigbe_mqtt_topic}/set\""
                    f", transformationPatternOut=\"JS:z2m-command-state.js\""
                    f"]"
                )
            # Device has switch (multi-gang) option
            if np.in1d(['plug_mt'], item['type']['types']).any():
                # Iterate through avaliable channels
                for channel_id, channel in item['channels'].items():
                    conf_str.append(
                        f"\t\tType switch : state_{channel_id} ["
                        f"stateTopic=\"{zigbe_mqtt_topic}\""
                        f", transformationPattern=\"JSONPATH:$.state_{channel_id}\""
                        f", commandTopic=\"{zigbe_mqtt_topic}/set\""
                        f", formatBeforePublish=\"{{\\\"state_{channel_id}\\\":\\\"%s\\\"}}\""
                        f"]"
                    )
            # Device has remote option
            if np.in1d(['remote'], item['type']['types']).any():
                conf_str.append(
                    f"\t\tType string : action [stateTopic=\"{zigbe_mqtt_topic}\", transformationPattern=\"JSONPATH:$.action\", trigger=true]")
            # Device has dimmer
            if np.in1d(['lamp'], item['type']['types']).any():
                conf_str.append(
                    f"\t\tType dimmer : dim ["
                    f"stateTopic=\"{zigbe_mqtt_topic}\""
                    f", transformationPattern=\"JSONPATH:$.brightness\""
                    f", commandTopic=\"{zigbe_mqtt_topic}/set\""
                    f", transformationPatternOut=\"JS:z2m-command-brightness.js\", min=1, max=255"
                    f"]"
                )
            # Device has Color Temp control
            if np.in1d(['ct'], item['type']['types']).any():
                conf_str.append(
                    f"\t\tType dimmer : ct ["
                    f"stateTopic=\"{zigbe_mqtt_topic}\""
                    f", transformationPattern=\"JSONPATH:$.color_temp\""
                    f", commandTopic=\"{zigbe_mqtt_topic}/set\""
                    f", transformationPatternOut=\"JS:z2m-command-color_temp.js\", min=150, max=500"
                    f"]"
                )
            # Device has Color control
            if np.in1d(['color'], item['type']['types']).any():
                conf_str.append(
                    f"\t\tType color : color ["
                    # f"stateTopic=\"{zigbe_mqtt_topic}\""
                    # f", transformationPattern=\"JSONPATH:$.color_xy\""
                    f", commandTopic=\"{zigbe_mqtt_topic}/set\""
                    f", transformationPatternOut=\"JS:z2m-command-color_xy.js\""
                    f"]"
                )
            # Device has Thermostat control
            if np.in1d(['thermostat'], item['type']['types']).any():
                conf_str.append(
                    f"\t\tType number : thermostat ["
                    f"stateTopic=\"{zigbe_mqtt_topic}\""
                    f", transformationPattern=\"JSONPATH:$.current_heating_setpoint\""
                    f", commandTopic=\"{zigbe_mqtt_topic}/set\""
                    f", transformationPatternOut=\"JS:z2m-command-thermostat-setpoint.js\""
                    f", unit=\"°C\""
                    f"]"
                )

            # Device has Position sensor
            if np.in1d(['position'], item['type']['types']).any():
                conf_str.append(
                    f"\t\tType number : position [stateTopic=\"{zigbe_mqtt_topic}\", transformationPattern=\"JSONPATH:$.position\"]")

            # Device has Contact sensor (inverse OPEN/CLOSE logic)
            if np.in1d(['contact'], item['type']['types']).any():
                conf_str.append(
                    f"\t\tType contact : contact [stateTopic=\"{zigbe_mqtt_topic}\", transformationPattern=\"JSONPATH:$.contact\", on=\"false\", off=\"true\"]")

            # Device has Motion sensor
            if np.in1d(['motion'], item['type']['types']).any():
                conf_str.append(
                    f"\t\tType switch : occupancy [stateTopic=\"{zigbe_mqtt_topic}\", transformationPattern=\"JSONPATH:$.occupancy\", on=\"true\", off=\"false\"]")
            # Device has Leak sensor
            if np.in1d(['leak'], item['type']['types']).any():
                conf_str.append(
                    f"\t\tType switch : leak [stateTopic=\"{zigbe_mqtt_topic}\", transformationPattern=\"JSONPATH:$.water_leak\", on=\"true\", off=\"false\"]")
            # Device has Temp sensor
            if np.in1d(['temperature'], item['type']['types']).any():
                conf_str.append(
                    f"\t\tType number : temperature [stateTopic=\"{zigbe_mqtt_topic}\", transformationPattern=\"JS:z2m-temperature.js\",unit=\"°C\"]")  # Could be different fields,sudo detect here

            if np.in1d(['humidity'], item['type']['types']).any():
                conf_str.append(
                    f"\t\tType number : humidity [stateTopic=\"{zigbe_mqtt_topic}\", transformationPattern=\"JSONPATH:$.humidity\"]")
            if np.in1d(['pressure'], item['type']['types']).any():
                conf_str.append(
                    f"\t\tType number : pressure [stateTopic=\"{zigbe_mqtt_topic}\", transformationPattern=\"JSONPATH:$.pressure\",unit=\"hPa\"]")
            # Some zigbee devices needs to be monitored
            if np.in1d(['activity'], item['type']['types']).any():
                conf_str.append(
                    f"\t\tType datetime : activity [stateTopic=\"{zigbe_mqtt_topic}\", transformationPattern=\"JS:z2m-activity.js\"]")
            # Some zigbee devices report battery OR battery_low signal
            if np.in1d(['battery'], item['type']['types']).any():
                conf_str.append(
                    f"\t\tType number : battery [stateTopic=\"{zigbe_mqtt_topic}\", transformationPattern=\"REGEX:(.*battery.*)∩JSONPATH:$.battery\"]")
                conf_str.append(
                    f"\t\tType switch : battery_low [stateTopic=\"{zigbe_mqtt_topic}\", transformationPattern=\"REGEX:(.*battery.*)∩JS:z2m-lowbatt.js\"]")
            else:
                if np.in1d(['battery_low'], item['type']['types']).any():
                    conf_str.append(
                        f"\t\tType switch : battery_low [stateTopic=\"{zigbe_mqtt_topic}\", transformationPattern=\"JSONPATH:$.battery_low\", on=\"true\", off=\"false\"]")
            # Some zigbee devices want custom battery signal
            if np.in1d(['battery_voltage'], item['type']['types']).any():
                batt_type = item['type']['batt_type']
                conf_str.append(
                    f"\t\tType switch : battery_low [stateTopic=\"{zigbe_mqtt_topic}\", transformationPattern=\"REGEX:(.*battery.*)∩JS:z2m-batt-low-{batt_type}.js\"]")
            # Some zigbee devices report battery voltage
            if np.in1d(['voltage'], item['type']['types']).any():
                conf_str.append(
                    f"\t\tType number : voltage [stateTopic=\"{zigbe_mqtt_topic}\", transformationPattern=\"JS:z2m-batt-mv.js\",unit=\"V\"]")
            # All zigbee devices have Link Quality reported
            conf_str.append(
                f"\t\tType number : link [stateTopic=\"{zigbe_mqtt_topic}\", transformationPattern=\"REGEX:(.*linkquality.*)∩JSONPATH:$.linkquality\"]")
            # All zigbee devices probably have some OTA updates reported
            conf_str.append(
                f"\t\tType switch : ota [stateTopic=\"{zigbe_mqtt_topic}\", transformationPattern=\"REGEX:(.*update_available.*)∩JSONPATH:$.update_available\", on=\"true\", off=\"false\"]")
            conf_str.append(
                f"}}")

        conf_str.append('')
    # Write config
    conf_str = '\n'.join(conf_str)
    print(conf_str)
    if args.write:
        f = open(os.path.join(ROOT_PATH, 'things', 'gen_things.things'), 'w')
        f.write(conf_str)
        f.close()

    # Generate ITEMS
    conf_str = [PREAMBULA]
    all_items = []
    gen_rules = [PREAMBULA]  # Special rules for devices
    for item in items:
        conf_str.extend(device_comment(item))
        device_items = {
            'item': item,
            'items': []
        }
        all_items.append(device_items)

        # Tasmota devices
        if np.in1d(['tasmota'], item['type']['types']).any():
            # Iterate through avaliable channels
            for channel in item['type']['tasmota_channels']:
                channel_cfg = item['channels'][channel['id']]
                device_icon = channel_cfg.get('icon', 'light')
                if 'expire' in channel_cfg:
                    device_timout = f", expire=\"{channel_cfg['expire']},command=OFF\""
                conf_str.append(
                    f"Switch {channel_cfg['id']} \"{channel_cfg['name']}\" <{device_icon}>"
                    f"{device_groups(item, channel['id'])}"
                    f" {{channel=\"mqtt:topic:openhab:{item['mqtt_topic']}:{channel['id']}\"{device_timout}}}"
                )
                device_items['items'].append(f"Switch item={item['id']}")

        # Generic devices

        # SOme device have switch (multi-gang) option
        if np.in1d(['plug_mt'], item['type']['types']).any():
            # Iterate through avaliable channels
            for channel_id, channel in item['channels'].items():
                device_icon = 'light'
                if 'icon' in channel:
                    device_icon = channel['icon']
                device_timout = ''
                if 'expire' in channel:
                    device_timout = f", expire=\"{channel['expire']},command=OFF\""
                conf_str.append(
                    f"Switch {channel['id']}_sw \"{channel['name']}\" <{device_icon}>"
                    f"{device_groups(channel,'sw')}"
                    f" {{channel=\"mqtt:topic:openhab:{item['mqtt_topic']}:state_{channel_id}\"{device_timout}}}"
                )
                device_items['items'].append(f"Switch item={channel['id']}_sw")

        # Some devices have switch option
        if np.in1d(['lamp', 'plug'], item['type']['types']).any():
            device_icon = 'switch'
            if 'lamp' in item['type']['types']:
                device_icon = 'light'
            device_timout = ''
            if 'expire' in item:
                device_timout = f", expire=\"{item['expire']},command=OFF\""
            conf_str.append(
                f"Switch {item['id']}_sw \"{item['name']}\" <{device_icon}>"
                f"{device_groups(item,'sw')}"
                f" {{channel=\"mqtt:topic:openhab:{item['mqtt_topic']}:state\"{device_timout}}}"
            )
            device_items['items'].append(f"Switch item={item['id']}_sw")
        # Some devices have thermostat
        if np.in1d(['thermostat'], item['type']['types']).any():
            device_icon = 'heatingt'
            conf_str.append(
                f"Number:Temperature {item['id']}_thermostat \"{item['name']} SET [%.0f %unit%]\" <{device_icon}>"
                f"{device_groups(item,'thermostat')}"
                f" {{channel=\"mqtt:topic:openhab:{item['mqtt_topic']}:thermostat\"}}"
            )
            device_items['items'].append(
                f"Setpoint item={item['id']}_thermostat minValue=5 maxValue=30 step=1")

        # Some devices have position option
        if np.in1d(['position'], item['type']['types']).any():
            device_icon = 'heating'
            conf_str.append(
                f"Number:Dimensionless {item['id']}_position \"{item['name']} POS [%.0f %%]\" <{device_icon}>"
                f"{device_groups(item,'position')}"
                f" {{channel=\"mqtt:topic:openhab:{item['mqtt_topic']}:position\"}}"
            )
            device_items['items'].append(
                f"Text item={item['id']}_position")

        # Some devices have contact option
        if np.in1d(['contact'], item['type']['types']).any():
            device_icon = 'door'
            conf_str.append(
                f"Contact {item['id']}_contact \"{item['name']} contact [%s]\" <{device_icon}>"
                f"{device_groups(item,'contact')}"
                f" {{channel=\"mqtt:topic:openhab:{item['mqtt_topic']}:contact\"}}"
            )
            device_items['items'].append(
                f"Text item={item['id']}_contact")

        # Some devices have motion option
        if np.in1d(['motion'], item['type']['types']).any():
            device_icon = 'motion'
            conf_str.append(
                f"Switch {item['id']}_occupancy \"{item['name']}\" <{device_icon}>"
                f"{device_groups(item,'occupancy')}"
                f" {{channel=\"mqtt:topic:openhab:{item['mqtt_topic']}:occupancy\"}}"
            )
            device_items['items'].append(f"Text item={item['id']}_occupancy")

        # Some devices have leak option
        if np.in1d(['leak'], item['type']['types']).any():
            device_icon = 'flow'
            conf_str.append(
                f"Switch {item['id']}_leak \"{item['name']}\" <{device_icon}>"
                f"{device_groups(item,'leak')}"
                f" {{channel=\"mqtt:topic:openhab:{item['mqtt_topic']}:leak\"}}"
            )
        # Some devices have Temperature option
        if np.in1d(['temperature'], item['type']['types']).any():
            device_icon = 'temperature'
            conf_str.append(
                f"Number:Temperature {item['id']}_temperature \"{item['name']} [%.0f %unit%]\" <{device_icon}>"
                f"{device_groups(item,'temperature')}"
                f" {{channel=\"mqtt:topic:openhab:{item['mqtt_topic']}:temperature\"}}"
            )
            device_items['items'].append(f"Text item={item['id']}_temperature")

        # Some devices have Humidity option
        if np.in1d(['humidity'], item['type']['types']).any():
            device_icon = 'humidity'
            conf_str.append(
                f"Number:Dimensionless {item['id']}_humidity \"{item['name']} [%.0f %%]\" <{device_icon}>"
                f"{device_groups(item,'humidity')}"
                f" {{channel=\"mqtt:topic:openhab:{item['mqtt_topic']}:humidity\"}}"
            )
            device_items['items'].append(f"Text item={item['id']}_humidity")
        # Some devices have Pressure option
        if np.in1d(['pressure'], item['type']['types']).any():
            device_icon = 'pressure'
            conf_str.append(
                f"Number:Pressure {item['id']}_pressure \"{item['name']} [%.0f %unit%]\" <{device_icon}>"
                f"{device_groups(item,'pressure')}"
                f" {{channel=\"mqtt:topic:openhab:{item['mqtt_topic']}:pressure\"}}"
            )
            device_items['items'].append(f"Text item={item['id']}_pressure")

        # Special WiFi things
        if np.in1d(['rssi'], item['type']['types']).any():
            device_icon = 'network'
            conf_str.append(
                f"Number:Dimensionless {item['id']}_rssi \"{item['name']} RSSI [%.0f]\" <{device_icon}>"
                f"{device_groups(item,'rssi')}"
                f" {{channel=\"mqtt:topic:openhab:{item['mqtt_topic']}:rssi\"}}"
            )
            device_items['items'].append(f"Text item={item['id']}_rssi")

        if np.in1d(['bssid'], item['type']['types']).any():
            device_icon = 'network'
            conf_str.append(
                f"String {item['id']}_bssid \"{item['name']} BSSID [%s]\" <{device_icon}>"
                f"{device_groups(item,'bssid')}"
                f" {{channel=\"mqtt:topic:openhab:{item['mqtt_topic']}:bssid\"}}"
            )
            device_items['items'].append(f"Text item={item['id']}_bssid")

        if np.in1d(['la'], item['type']['types']).any():
            device_icon = 'energy'
            conf_str.append(
                f"Number:Dimensionless {item['id']}_la \"{item['name']} LA [%d]\" <{device_icon}>"
                f"{device_groups(item,'la')}"
                f" {{channel=\"mqtt:topic:openhab:{item['mqtt_topic']}:la\"}}"
            )
            device_items['items'].append(f"Text item={item['id']}_la")

        # Some devices report activity
        if 'activity' in item['type']['types']:
            conf_str.append(
                f"DateTime {item['id']}_activity \"{item['name']} [JS(display-activity.js):%s]\""
                f" <time> (g_device_activity) {{channel=\"mqtt:topic:openhab:{item['mqtt_topic']}:activity\"}}"
            )

        # Special Zigbee things
        if np.in1d(['zigbee'], item['type']['types']).any():
            # All Zigbee lamps have dimmer built-in
            if np.in1d(['lamp'], item['type']['types']).any():
                conf_str.append(
                    f"Dimmer {item['id']}_dim \"{item['name']} DIM [%d %%]\" <{device_icon}>"
                    f"{device_groups(item,'dim')}"
                    f" {{channel=\"mqtt:topic:openhab:{item['mqtt_topic']}:dim\"}}"
                )
                device_items['items'].append(f"Slider item={item['id']}_dim")

            # Zigbee color temperature
            if np.in1d(['ct'], item['type']['types']).any():
                conf_str.append(
                    f"Dimmer {item['id']}_ct \"{item['name']} CT [JS(display-mired.js):%s]\" <colorwheel>"
                    f"{device_groups(item,'ct')}"
                    f" {{channel=\"mqtt:topic:openhab:{item['mqtt_topic']}:ct\"}}"
                )
                device_items['items'].append(f"Slider item={item['id']}_ct")
                gen_rules.append(
                    f"""
// Device should apply saved color temp when ON
rule "{item['name']} apply color on ON"
when
    Item {item['id']}_sw changed to ON
then
	{item['id']}_ct.sendCommand({item['id']}_ct.state as Number)
end
"""
                )
            # Zigbee color
            if np.in1d(['color'], item['type']['types']).any():
                conf_str.append(
                    f"Color {item['id']}_color \"{item['name']} Color\" <colorwheel>"
                    f"{device_groups(item,'color')}"
                    f" {{channel=\"mqtt:topic:openhab:{item['mqtt_topic']}:color\"}}"
                )
                device_items['items'].append(f"Colorpicker item={item['id']}_color")

            # All zigbee devices have Link Quality reported
            conf_str.append(
                f"Number:Dimensionless {item['id']}_link \"{item['name']} LINK [%d]\""
                f" <linkz> (g_zigbee_link) {{channel=\"mqtt:topic:openhab:{item['mqtt_topic']}:link\"}}"
            )
            device_items['items'].append(
                f"Text item={item['id']}_link icon=\"linkz\"")

            # All zigbee devices probably have some OTA updates reported
            conf_str.append(
                f"Switch {item['id']}_ota \"{item['name']} OTA [%s]\""
                f" <fire> (g_zigbee_ota) {{channel=\"mqtt:topic:openhab:{item['mqtt_topic']}:ota\"}}"
            )
            device_items['items'].append(
                f"Text item={item['id']}_ota icon=\"fire\"")

            # Some zigbee devices report battery
            if 'battery' in item['type']['types']:
                conf_str.append(
                    f"Number:Dimensionless {item['id']}_battery \"{item['name']} [%.0f %%]\""
                    f" <battery> (g_battery_level) {{channel=\"mqtt:topic:openhab:{item['mqtt_topic']}:battery\"}}"
                )
            if np.in1d(['battery', 'battery_low', 'battery_voltage'], item['type']['types']).any():
                conf_str.append(
                    f"Switch {item['id']}_battery_low \"{item['name']} [MAP(lowbat.map):%s]\""
                    f" <lowbattery> (g_battery_low) {{channel=\"mqtt:topic:openhab:{item['mqtt_topic']}:battery_low\"}}"
                )

            # ... and it's voltage
            if 'voltage' in item['type']['types']:
                conf_str.append(
                    f"Number:ElectricPotential {item['id']}_voltage \"{item['name']} [%.0f mV]\""
                    f" <energy> (g_battery_voltage) {{channel=\"mqtt:topic:openhab:{item['mqtt_topic']}:voltage\"}}"
                )

        conf_str.append('')
    # Write config
    conf_str = '\n'.join(conf_str)
    print(conf_str)
    if args.write:
        f = open(os.path.join(ROOT_PATH, 'items', 'gen_items.items'), 'w')
        f.write(conf_str)
        f.close()

    print(all_items)

    # Write test sitemap
    test_sitemap = PREAMBULA + """
sitemap gen label="GEN ITEMS"
{
"""
    for gen_item in all_items:
        if not gen_item['items']:
            continue
        test_sitemap += f"Frame label=\"{device_label(gen_item['item'])}\" {{\n"
        test_sitemap += "\n".join(gen_item['items'])
        test_sitemap += "\n}\n"

    test_sitemap += """
}
"""

    print(test_sitemap)
    if args.write:
        f = open(os.path.join(ROOT_PATH, 'sitemaps', 'gen.sitemap'), 'w')
        f.write(test_sitemap)
        f.close()

    # Write generated rules
    gen_rules = '\n'.join(gen_rules)
    print(gen_rules)
    if args.write:
        f = open(os.path.join(ROOT_PATH, 'rules', 'gen_auto.rules'), 'w')
        f.write(gen_rules)
        f.close()

    # (re)Generate Zigbee devices list
    if args.write:
        device_yaml = {}
        # Load old devices config
        # Don not load enymore. Build our own new from config
        # device_yaml = yaml.load(
        #     open(
        #         os.path.join(ROOT_PATH, 'devices.yaml'),
        #         'r'
        #     ),
        #     Loader=yaml.FullLoader
        # )

        # Check existing list
        for zigbee_id, zigbee_name in zigbee_devices_list.items():
            if zigbee_id in device_yaml:
                device_yaml[zigbee_id]['friendly_name'] = zigbee_name
            else:
                device_yaml[zigbee_id] = {'friendly_name': zigbee_name}

        yaml.dump(
            device_yaml,
            open(
                os.path.join(ROOT_PATH, 'devices.yaml'),
                'w'
            )
        )
