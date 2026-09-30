> For the complete documentation index, see [llms.txt](https://docs.holybro.com/llms.txt). Markdown versions of documentation pages are available by appending `.md` to page URLs; this page is available as [Markdown](https://docs.holybro.com/autopilot/pixhawk-baseboards/pixhawk-jetson-baseboard/overview-and-specification.md).

# Overview & Specification

## **Features**

* Fully compatible with Jetson Orin NX/Nano
* Combines the power of Pixhawk & Jetson in a small form factor
* [**Pixhawk Bus (PAB) open source specification**](https://github.com/pixhawk/Pixhawk-Standards/blob/master/DS-010%20Pixhawk%20Autopilot%20Bus%20Standard.pdf)
* Jetson & controller are connected via UART, CAN, and Ethernet Switch

{% hint style="info" %}

#### Jetson Xaviar NX and Jetson Nano are not compatible.

#### This baseboard will function as a Jetson Carrier without the Flight Controller

{% endhint %}

## Jetson Orin NX/Nano Connectors

* Gigabit Ethernet &#x20;
  * Connected to both Jetson & controller via Ethernet Switch (RTL8367S) - 8-pin JST-GH - RJ45
    * Ethernet port & switch powered by the circuit as the Pixhawk&#x20;
  * 8-pin JST-GH
  * RJ45
* 2x MIPI CSI Camera Inputs
  * 4 Lanes each
  * 22-Pin Raspberry Pi Cam FFC
* 2x USB 3.2 Host Port
  * USB A
  * 1.5A Current Limit
* 2x USB 2.0 Host Port
  * 5-Pin JST-GH
  * 1.0A Current Limit
* USB 2.0 for Programming/debugging
  * USB-C
* M.2 Key M 2242/2280 for NVMe SSD
  * PCIEx4
* M.2 Key E 2230 for WiFi/BT
  * PCIEx2
  * USB
  * UART
  * I2S
* Mini HDMI Out
* 4x GPIO
  * 6-pin JST-GH
* CAN Port
  * Connected to the controller’s CAN2 (4 Pin JST-GH)
* SPI Port
  * 7-Pin JST-GH
* I2C Port
  * 4-Pin JST-GH
* I2S Port
  * 7-Pin JST-GH
* 2x UART Port
  * 1 for debug
  * 1 connected to the controller’s telem2
* Fan Power Port
  * Current limit 0.35A
* IIM42652 IMU
* Input Power
  * XT30 Connector
  * Voltage Rating: 7V-24V (2S-5S)
  * Separate the input power circuits from the controller to ensure flight safety
  * Holybro UBEC can be used for applications above 4S
  * **Note:** The Pixhawk Jetson Baseboard has an integrated UBEC to convert 7V-24V to 5.0V for the Jetson. Using an external UBEC alongside the integrated one provides redundancy and easier replacement in case of BEC failure.
* Power Requirements
  * Depends on Usage and Peripherals, minimum \~15-30 watts

## Flight Controller Connectors

* Pixhawk Bus Interface - 100 Pin Hirose DF40 - 50 Pin Hirose DF40
  * [Pixhawk Bus (PAB) Form Factor](https://github.com/pixhawk/Pixhawk-Standards/blob/master/DS-010%20Pixhawk%20Autopilot%20Bus%20Standard.pdf)
* Redundant Digital Power Module Inputs
  * I2C Power Monitor Support
  * 2x – 6 Pin Molex CLIK-Mate
  * Power Path Selector w/ Overvoltage Protection
* Voltage Ratings:
  * Max input voltage: 6V
  * USB Power Input: 4.75\~5.25V
* 2 GPS Port
  * GPS1 - GPS Plus Safety Switch Port (10-Pin JST-GH)
  * GPS2 - basic GPS Port (6-pin JST-GH)
* 2x CAN Ports
  * 4 Pin JST-GH
* 3x Telemetry Ports with Flow Control
  * 2x 6-Pin JST-GH
  * 1 is connected to Jetson’s UART1 Port
* 16 PWM Outputs
  * 2x 10-Pin JST-GH
* UART4 & I2C Port
  * 6-Pin JST-GH
* Gigabit Ethernet port
  * Connected to both Jetson & controller via Ethernet Switch (RTL8367S)
  * 8-pin JST-GH
  * RJ45
* AD & IO
  * 8-Pin JST-GH
* USB 2.0
  * USB-C
  * 4-pin JST-GH
* DSM Input
  * 3-pin JST-ZH 1.5mm Pitch
* RC in
  * PPM/SBUS
  * 5-pin JST-GH
* SPI Port
  * External Sensor Bus (SPI5aut
  * 11-Pin JST-GH
* 2x Debug Port
  * 1 for FMU
  * 1 for IO
  * 10-Pin JST-SH
* Current Ratings:
  * Telem1 output current limiter: 1.5A
  * All other port combined output current limiter: 1.5A

{% embed url="<https://docs.holybro.com/autopilot/pixhawk-baseboards/pixhawk-jetson-baseboard/dimension>" %}


---

# Agent Instructions
This documentation is published with GitBook. GitBook is the documentation platform designed so that both humans and AI agents can read, navigate, and reason over technical content effectively. Learn more at gitbook.com.

## Querying This Documentation
If you need additional information that is not directly available in this page, you can query the documentation dynamically by asking a question.

Perform an HTTP GET request on the current page URL with the `ask` query parameter, and the optional `goal` query parameter:

```
GET https://docs.holybro.com/autopilot/pixhawk-baseboards/pixhawk-jetson-baseboard/overview-and-specification.md?ask=<question>&goal=<endgoal>
```

`ask` is the immediate question: it should be specific, self-contained, and written in natural language.
`goal` is optional and describes the broader end goal you are ultimately trying to accomplish on behalf of the user. GitBook uses it to tailor the answer towards what is most useful for that goal.

The response will contain a direct answer to the question and relevant excerpts and sources from the documentation.

Use this mechanism when the answer is not explicitly present in the current page, you need clarification or additional context, or you want to retrieve related documentation sections.
