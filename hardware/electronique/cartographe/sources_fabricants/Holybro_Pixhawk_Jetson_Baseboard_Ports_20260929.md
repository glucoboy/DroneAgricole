> For the complete documentation index, see [llms.txt](https://docs.holybro.com/llms.txt). Markdown versions of documentation pages are available by appending `.md` to page URLs; this page is available as [Markdown](https://docs.holybro.com/autopilot/pixhawk-baseboards/pixhawk-jetson-baseboard/ports-pinout.md).

# Ports Pinout

<figure><img src="https://2367252986-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FLIgtGDAvVGkCKGOJb1bR%2Fuploads%2FPQPu6PDjpNCoCGZiQdoa%2FJetson%20Pinout.jpg?alt=media&amp;token=1e970d9c-4667-43c5-b95a-165673ecce10" alt=""><figcaption></figcaption></figure>

{% hint style="info" %}

* I/O PWM OUT = MAIN OUT
* FMU PWM OUT = AUX OUT
* Pin 1 starts from the flight controllers like diagram below

![](https://2367252986-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FLIgtGDAvVGkCKGOJb1bR%2Fuploads%2FoUfIkAIADuuZRcSTj2Cr%2FPin%20Order.jpg?alt=media\&token=e18c4309-6ba7-4db2-8d74-aca454a912f7)
{% endhint %}

### Power 1 (Main), Power 2 Ports&#x20;

(2.00mm Pitch CLIK-Mate)

<table data-header-hidden data-search="false"><thead><tr><th></th><th></th><th></th></tr></thead><tbody><tr><td>Pin </td><td>Signal </td><td>Voltage </td></tr><tr><td>1(red) </td><td>VDD5V_BRICK1/2(in) </td><td>+5V </td></tr><tr><td>2(black) </td><td>VDD5V_BRICK1/2 (in) </td><td>+5V </td></tr><tr><td>3(black) </td><td>SCL1/2 </td><td>+3.3V </td></tr><tr><td>4(black) </td><td>SDA1/2</td><td>+3.3V </td></tr><tr><td>5(black) </td><td>GND </td><td>GND </td></tr><tr><td>6(black) </td><td>GND </td><td>GND </td></tr></tbody></table>

### Tel1, Tel3 Ports

<table data-header-hidden data-search="false"><thead><tr><th></th><th></th><th></th></tr></thead><tbody><tr><td>Pin </td><td>Signal </td><td>Voltage </td></tr><tr><td>1(red) </td><td>VCC (out) </td><td>+5V </td></tr><tr><td>2(black) </td><td>TX7/2(out) </td><td>+3.3V </td></tr><tr><td>3(black) </td><td>RX7/2(in) </td><td>+3.3V </td></tr><tr><td>4(black) </td><td>CTS7/2(in) </td><td>+3.3V </td></tr><tr><td>5(black) </td><td>RTS7/2(out) </td><td>+3.3V </td></tr><tr><td>6(black) </td><td>GND </td><td>GND </td></tr></tbody></table>

### CAN1, CAN2 Ports

| Pin      | Signal    | Voltage |
| -------- | --------- | ------- |
| 1(red)   | VCC (out) | +5V     |
| 2(black) | CANH1/2   | +3.3V   |
| 3(black) | CANL1/2   | +3.3V   |
| 4(black) | GND       | GND     |

### GPS1 Port

<table data-header-hidden data-search="false"><thead><tr><th></th><th></th><th></th></tr></thead><tbody><tr><td>Pin </td><td>Signal </td><td>Voltage </td></tr><tr><td>1(red) </td><td>VCC (out) </td><td>+5V </td></tr><tr><td>2 black) </td><td>TX1(out) </td><td>+3.3V </td></tr><tr><td>3(black) </td><td>RX1(in) </td><td>+3.3V </td></tr><tr><td>4(black) </td><td>SCL1 </td><td>+3.3V </td></tr><tr><td>5(black) </td><td>SDA1 </td><td>+3.3V </td></tr><tr><td>6(black) </td><td>SAFETY_SWITCH </td><td>+3.3V </td></tr><tr><td>7(black) </td><td>SAFETY_SWITCH_LED </td><td>+3.3V </td></tr><tr><td>8(black) </td><td>VDD_3V3 </td><td>+3.3V </td></tr><tr><td>9(black) </td><td>BUZZER- </td><td>0~5V </td></tr><tr><td>10(black) </td><td>GND </td><td>GND </td></tr></tbody></table>

### GPS2 Port

<table data-header-hidden data-search="false"><thead><tr><th></th><th></th><th></th></tr></thead><tbody><tr><td>Pin </td><td>Signal </td><td>Voltage </td></tr><tr><td>1(red) </td><td>VCC (out) </td><td>+5V </td></tr><tr><td>2 black) </td><td>TX8(out)</td><td>+3.3V </td></tr><tr><td>3(black) </td><td>RX8(in)</td><td>+3.3V </td></tr><tr><td>4(black) </td><td>SCL2</td><td>+3.3V </td></tr><tr><td>5(black) </td><td>SDA2</td><td>+3.3V </td></tr><tr><td>6(black) </td><td>GND </td><td>GND </td></tr></tbody></table>

### UART4 & I2C Port&#x20;

(also shown as UART\&I2C on some board)

<table data-header-hidden data-search="false"><thead><tr><th></th><th></th><th></th></tr></thead><tbody><tr><td>Pin </td><td>Signal </td><td>Voltage </td></tr><tr><td>1(red) </td><td>VCC (out) </td><td>+5V </td></tr><tr><td>2(black) </td><td>TX4(out) </td><td>+3.3V </td></tr><tr><td>3(black) </td><td>RX4(in) </td><td>+3.3V </td></tr><tr><td>4(black) </td><td>SCL3</td><td>+3.3V</td></tr><tr><td>5(black) </td><td>SDA3 </td><td>+3.3V</td></tr><tr><td>6(black) </td><td>NFC_GPIO </td><td>+3.3V </td></tr><tr><td>7(black)</td><td>GND</td><td>GND</td></tr></tbody></table>

### SPI Port

<table data-header-hidden data-search="false"><thead><tr><th></th><th></th><th></th></tr></thead><tbody><tr><td>Pin </td><td>Signal </td><td>Voltage </td></tr><tr><td>1(red) </td><td>VCC (out) </td><td>+5V </td></tr><tr><td>2 (black) </td><td>SPI6_SCK </td><td>+3.3V </td></tr><tr><td>3(black) </td><td>SPI6_MISO </td><td>+3.3V </td></tr><tr><td>4(black) </td><td>SPI6_MOSI </td><td>+3.3V </td></tr><tr><td>5(black) </td><td>SPI6_CS1 </td><td>+3.3V </td></tr><tr><td>6(black) </td><td>SPI6_CS2 </td><td>+3.3V </td></tr><tr><td>7(black) </td><td>SPIX_SYNC </td><td>+3.3V  </td></tr><tr><td>8(black) </td><td>SPI6_DRDY1</td><td>+3.3V</td></tr><tr><td>9(black) </td><td>SPI6_DRDY2</td><td>+3.3V</td></tr><tr><td>10(black) </td><td>SPI6_nRESET</td><td>+3.3V</td></tr><tr><td>11(black) </td><td>GND </td><td>GND </td></tr></tbody></table>

### FMU USB Port

| Pin      | Signal    | Voltage |
| -------- | --------- | ------- |
| 1(red)   | VBUS (in) | +5V     |
| 2(black) | DM        | +3.3V   |
| 3(black) | DP        | +3.3V   |
| 4(black) | GND       | GND     |

### I2C Port

| Pin      | Signal | Voltage |
| -------- | ------ | ------- |
| 1(red)   | VCC    | +5V     |
| 2(black) | SCL3   | +3.3V   |
| 3(black) | SDA3   | +3.3V   |
| 4(black) | GND    | GND     |

### ETH-P1 Port

<table data-header-hidden data-search="false"><thead><tr><th></th><th></th><th></th></tr></thead><tbody><tr><td>Pin </td><td>Signal </td><td>Voltage </td></tr><tr><td>1(red) </td><td>TX_D1+</td><td>-</td></tr><tr><td>2(black) </td><td>TX_D1-</td><td>-</td></tr><tr><td>3(black) </td><td>RX_D2+</td><td>-</td></tr><tr><td>4(black) </td><td>RX_D2-</td><td>-</td></tr><tr><td>5(black) </td><td>Bi_D3+</td><td>-</td></tr><tr><td>6(black) </td><td>Bi_D3-</td><td>-</td></tr><tr><td>7(black) </td><td>Bi_D4+</td><td>-</td></tr><tr><td>8(black) </td><td>Bi_D4-</td><td>-</td></tr></tbody></table>

### IO Debug Port

(JST-SH 1mm Pitch)

<table data-header-hidden data-search="false"><thead><tr><th></th><th></th><th></th></tr></thead><tbody><tr><td>Pin </td><td>Signal </td><td>Voltage </td></tr><tr><td>1(red) </td><td>IO_VDD_3V3(out) </td><td>+3.3V </td></tr><tr><td>2 black) </td><td>IO_USART1_TX</td><td>+3.3V </td></tr><tr><td>3(black) </td><td>NC </td><td>--</td></tr><tr><td>4(black) </td><td>IO_SWD_IO</td><td>+3.3V </td></tr><tr><td>5(black) </td><td>IO_SWD_CK</td><td>+3.3V </td></tr><tr><td>6(black) </td><td>IO_SWO</td><td>+3.3V </td></tr><tr><td>7(black) </td><td>IO_SPARE_GPIO1 </td><td>+3.3V </td></tr><tr><td>8(black) </td><td>IO_SPARE_GPIO2</td><td>+3.3V </td></tr><tr><td>9(black) </td><td>IO_nRST</td><td>+3.3V</td></tr><tr><td>10(black) </td><td>GND </td><td>GND </td></tr></tbody></table>

### FMU Debug Port

(JST-SH 1mm Pitch)

<table data-header-hidden data-search="false"><thead><tr><th></th><th></th><th></th></tr></thead><tbody><tr><td>Pin </td><td>Signal </td><td>Voltage </td></tr><tr><td>1(red) </td><td>FMU_VDD_3V3(out) </td><td>+3.3V </td></tr><tr><td>2( black) </td><td>FMU_USART3_TX</td><td>+3.3V </td></tr><tr><td>3(black) </td><td>FMU_USART3_RX </td><td>+3.3V</td></tr><tr><td>4(black) </td><td>FMU_SWD_IO</td><td>+3.3V </td></tr><tr><td>5(black) </td><td>FMU_SWD_CK</td><td>+3.3V </td></tr><tr><td>6(black) </td><td>SPI6_SCK_EXTERNAL1</td><td>+3.3V </td></tr><tr><td>7(black) </td><td>NFC_GPIO</td><td>+3.3V </td></tr><tr><td>8(black) </td><td>PH11</td><td>+3.3V </td></tr><tr><td>9(black) </td><td>FMU_nRST</td><td>+3.3V</td></tr><tr><td>10(black) </td><td>GND </td><td>GND </td></tr></tbody></table>

### AD\&IO port

<table data-header-hidden data-search="false"><thead><tr><th></th><th></th><th></th></tr></thead><tbody><tr><td>Pin </td><td>Signal </td><td>Voltage </td></tr><tr><td>1(red) </td><td>VCC (out) </td><td>+5V </td></tr><tr><td>2(black) </td><td>FMU_CAP1 </td><td>+3.3V </td></tr><tr><td>3(black) </td><td>FMU_BOOTLOADER </td><td>+3.3V </td></tr><tr><td>4(black) </td><td>FMU_RST_REQ</td><td>+3.3V</td></tr><tr><td>5(black) </td><td>NARMED </td><td>+3.3V</td></tr><tr><td>6(black) </td><td>ADC1_3V3 </td><td>+3.3V </td></tr><tr><td>7(black)</td><td>ADC1_6V6</td><td>+6.6V</td></tr><tr><td>8(black)</td><td>GND</td><td>GND</td></tr></tbody></table>

### DSM RC Port

(JST-ZH 1.5mm Pitch)

| Pin       | Signal             | Voltage |
| --------- | ------------------ | ------- |
| 1(yellow) | VDD\_3V3\_SPEKTRUM | +3.3V   |
| 2(black)  | GND                | GND     |
| 3(gray)   | DSM/Spektrum  in   | +3.3V   |

### RC IN Port

| Pin       | Signal             | Voltage |
| --------- | ------------------ | ------- |
| 1(red)    | VDD\_5V \_RC (out) | +5V     |
| 2( black) | SBUS/PPM in        | +3.3V   |
| 3( black) | RSSI\_IN           | +3.3V   |
| 4( black) | NC                 | --      |
| 5( black) | GND                | GND     |

### SBUS Out Port

| Pin       | Signal    | Voltage |
| --------- | --------- | ------- |
| 1(red)    | NC        | --      |
| 2( black) | SBUS\_OUT | +3.3V   |
| 3( black) | GND       | GND     |

### FMU PWM OUT (AUX OUT)

<table data-header-hidden data-search="false"><thead><tr><th></th><th></th><th></th></tr></thead><tbody><tr><td>Pin </td><td>Signal </td><td>Voltage </td></tr><tr><td>1(red) </td><td>VDD_SERVO </td><td>0~16V</td></tr><tr><td>2(black)</td><td>FMU_CH1</td><td>+3.3V </td></tr><tr><td>3(black)</td><td>FMU_CH2</td><td>+3.3V</td></tr><tr><td>4(black)</td><td>FMU_CH3</td><td>+3.3V</td></tr><tr><td>5(black)</td><td>FMU_CH4</td><td>+3.3V</td></tr><tr><td>6(black)</td><td>FMU_CH5</td><td>+3.3V</td></tr><tr><td>7(black)</td><td>FMU_CH6</td><td>+3.3V</td></tr><tr><td>8(black)</td><td>FMU_CH7</td><td>+3.3V</td></tr><tr><td>9(black)</td><td>FMU_CH8</td><td>+3.3V</td></tr><tr><td>10(black)</td><td>GND</td><td>GND</td></tr></tbody></table>

### IO PWM OUT (MAIN OUT)

<table data-header-hidden data-search="false"><thead><tr><th></th><th></th><th></th></tr></thead><tbody><tr><td>Pin </td><td>Signal </td><td>Voltage </td></tr><tr><td>1(red) </td><td>VDD_SERVO </td><td>0~16V</td></tr><tr><td>2(black)</td><td>IO_CH1</td><td>+3.3V </td></tr><tr><td>3(black)</td><td>IO_CH2</td><td>+3.3V</td></tr><tr><td>4(black)</td><td>IO_CH3</td><td>+3.3V</td></tr><tr><td>5(black)</td><td>IO_CH4</td><td>+3.3V</td></tr><tr><td>6(black)</td><td>IO_CH5</td><td>+3.3V</td></tr><tr><td>7(black)</td><td>IO_CH6</td><td>+3.3V</td></tr><tr><td>8(black)</td><td>IO_CH7</td><td>+3.3V</td></tr><tr><td>9(black)</td><td>IO_CH8</td><td>+3.3V</td></tr><tr><td>10(black)</td><td>GND</td><td>GND</td></tr></tbody></table>

### Orin USB2.0 Port&#x20;

| Pin      | Signal          | Voltage |
| -------- | --------------- | ------- |
| 1(red)   | USB\_VBUS (out) | +5V     |
| 2(black) | DM              | +3.3V   |
| 3(black) | DP              | +3.3V   |
| 4(black) | GND             | GND     |
| 5(black) | Shield          | GND     |

### Orin Debug

(JST-SH 1mm Pitch)

<table data-header-hidden data-search="false"><thead><tr><th></th><th></th><th></th></tr></thead><tbody><tr><td>Pin </td><td>Signal </td><td>Voltage </td></tr><tr><td>1(red) </td><td>VCC (out)</td><td>+5V</td></tr><tr><td>2(black)</td><td>Orin_UART2_TXD</td><td>+3.3V </td></tr><tr><td>3(black)</td><td>Orin_UART2_RXD</td><td>+3.3V</td></tr><tr><td>4(black)</td><td>NC</td><td>--</td></tr><tr><td>5(black)</td><td>NC</td><td>--</td></tr><tr><td>6(black)</td><td>GND</td><td>GND</td></tr></tbody></table>

### Orin I2C Port

| Pin      | Signal          | Voltage |
| -------- | --------------- | ------- |
| 1(red)   | VCC (out)       | +5V     |
| 2(black) | Orin\_I2C1\_SCL | +3.3V   |
| 3(black) | Orin\_I2C1\_SDA | +3.3V   |
| 4(black) | GND             | GND     |

### Orin GPIO Port

<table data-header-hidden data-search="false"><thead><tr><th></th><th></th><th></th></tr></thead><tbody><tr><td>Pin </td><td>Signal </td><td>Voltage </td></tr><tr><td>1(red) </td><td>VCC</td><td>+5V</td></tr><tr><td>2(black)</td><td>Orin_GPIO_07</td><td>+3.3V </td></tr><tr><td>3(black)</td><td>Orin_GPIO_11</td><td>+3.3V</td></tr><tr><td>4(black)</td><td>Orin_GPIO_12</td><td>+3.3V</td></tr><tr><td>5(black)</td><td>Orin_GPIO_13</td><td>+3.3V</td></tr><tr><td>6(black)</td><td>GND</td><td>GND</td></tr></tbody></table>

### Orin Camera0 Port&#x20;

Camera Serial Interface (CSI)

<table data-header-hidden data-search="false"><thead><tr><th></th><th></th><th></th></tr></thead><tbody><tr><td>Pin </td><td>Signal </td><td>Voltage </td></tr><tr><td>1</td><td>GND</td><td>GND</td></tr><tr><td>2</td><td>Orin_CSI1_D0_N</td><td>+3.3V </td></tr><tr><td>3</td><td>Orin_CSI1_D0_P</td><td>+3.3V</td></tr><tr><td>4</td><td>GND</td><td>GND</td></tr><tr><td>5</td><td>Orin_CSI1_D1_N</td><td>+3.3V</td></tr><tr><td>6</td><td>Orin_CSI1_D1_P</td><td>+3.3V</td></tr><tr><td>7</td><td>GND</td><td>GND</td></tr><tr><td>8</td><td>Orin_CSI1_CLK_N</td><td>+3.3V</td></tr><tr><td>9</td><td>Orin_CSI1_CLK_P</td><td>+3.3V</td></tr><tr><td>10</td><td>GND</td><td>GND</td></tr><tr><td>11</td><td>Orin_CSI0_D0_N</td><td>+3.3V </td></tr><tr><td>12</td><td>Orin_CSI0_D0_P</td><td>+3.3V</td></tr><tr><td>13</td><td>GND</td><td>GND</td></tr><tr><td>14</td><td>Orin_CSI0_D1_N</td><td>+3.3V </td></tr><tr><td>15</td><td>Orin_CSI0_D1_P</td><td>+3.3V</td></tr><tr><td>16</td><td>GND</td><td>GND</td></tr><tr><td>17</td><td>Orin_CAM0_PWDN</td><td>+3.3V</td></tr><tr><td>18</td><td>Orin_CAM0_MCLK</td><td>+3.3V</td></tr><tr><td>19</td><td>GND</td><td>GND</td></tr><tr><td>20</td><td>Orin_CAM0_I2C_SCL</td><td>+3.3V</td></tr><tr><td>21</td><td>Orin_CAM0_I2C_SDA</td><td>+3.3V</td></tr><tr><td>22</td><td>VDD</td><td>+3.3V</td></tr></tbody></table>

### Orin Camera1 Port

Camera Serial Interface (CSI)

<table data-header-hidden data-search="false"><thead><tr><th></th><th></th><th></th></tr></thead><tbody><tr><td>Pin </td><td>Signal </td><td>Voltage </td></tr><tr><td>1</td><td>GND</td><td>GND</td></tr><tr><td>2</td><td>Orin_CSI2_D0_N</td><td>+3.3V </td></tr><tr><td>3</td><td>Orin_CSI2_D0_P</td><td>+3.3V</td></tr><tr><td>4</td><td>GND</td><td>GND</td></tr><tr><td>5</td><td>Orin_CSI2_D1_N</td><td>+3.3V</td></tr><tr><td>6</td><td>Orin_CSI2_D1_P</td><td>+3.3V</td></tr><tr><td>7</td><td>GND</td><td>GND</td></tr><tr><td>8</td><td>Orin_CSI2_CLK_N</td><td>+3.3V</td></tr><tr><td>9</td><td>Orin_CSI2_CLK_P</td><td>+3.3V</td></tr><tr><td>10</td><td>GND</td><td>GND</td></tr><tr><td>11</td><td>Orin_CSI3_D0_N</td><td>+3.3V </td></tr><tr><td>12</td><td>Orin_CSI3_D0_P</td><td>+3.3V</td></tr><tr><td>13</td><td>GND</td><td>GND</td></tr><tr><td>14</td><td>Orin_CSI3_D1_N</td><td>+3.3V </td></tr><tr><td>15</td><td>Orin_CSI3_D1_P</td><td>+3.3V</td></tr><tr><td>16</td><td>GND</td><td>GND</td></tr><tr><td>17</td><td>Orin_CAM1_PWDN</td><td>+3.3V</td></tr><tr><td>18</td><td>Orin_CAM1_MCLK</td><td>+3.3V</td></tr><tr><td>19</td><td>GND</td><td>GND</td></tr><tr><td>20</td><td>Orin_CAM1_I2C_SCL</td><td>+3.3V</td></tr><tr><td>21</td><td>Orin_CAM1_I2C_SDA</td><td>+3.3V</td></tr><tr><td>22</td><td>VDD</td><td>+3.3V</td></tr></tbody></table>

### Orin SPI Port

<table data-header-hidden data-search="false"><thead><tr><th></th><th></th><th></th></tr></thead><tbody><tr><td>Pin </td><td>Signal </td><td>Voltage </td></tr><tr><td>1(red) </td><td>VCC</td><td>+5V</td></tr><tr><td>2(black)</td><td>Orin_SPI0_SCK</td><td>+3.3V </td></tr><tr><td>3(black)</td><td>Orin_SPI0_MISO</td><td>+3.3V</td></tr><tr><td>4(black)</td><td>Orin_SPI0_MOSI</td><td>+3.3V</td></tr><tr><td>5(black)</td><td>Orin_SPI0_CS0</td><td>+3.3V</td></tr><tr><td>6(black)</td><td>Orin_SPI0_CS1</td><td>+3.3V</td></tr><tr><td>7(black)</td><td>GND</td><td>GND</td></tr></tbody></table>

### Orin I2S Port

<table data-header-hidden data-search="false"><thead><tr><th></th><th></th><th></th></tr></thead><tbody><tr><td>Pin </td><td>Signal </td><td>Voltage </td></tr><tr><td>1(red) </td><td>VCC</td><td>+5V</td></tr><tr><td>2(black)</td><td>Orin_I2S0_SDOUT</td><td>+3.3V </td></tr><tr><td>3(black)</td><td>Orin_I2S0_SDIN</td><td>+3.3V</td></tr><tr><td>4(black)</td><td>Orin_I2S0_LRCK</td><td>+3.3V</td></tr><tr><td>5(black)</td><td>Orin_I2S0_SCLK</td><td>+3.3V</td></tr><tr><td>6(black)</td><td>Orin_GPIO_09</td><td>+3.3V</td></tr><tr><td>7(black)</td><td>GND</td><td>GND</td></tr></tbody></table>


---

# Agent Instructions
This documentation is published with GitBook. GitBook is the documentation platform designed so that both humans and AI agents can read, navigate, and reason over technical content effectively. Learn more at gitbook.com.

## Querying This Documentation
If you need additional information that is not directly available in this page, you can query the documentation dynamically by asking a question.

Perform an HTTP GET request on the current page URL with the `ask` query parameter, and the optional `goal` query parameter:

```
GET https://docs.holybro.com/autopilot/pixhawk-baseboards/pixhawk-jetson-baseboard/ports-pinout.md?ask=<question>&goal=<endgoal>
```

`ask` is the immediate question: it should be specific, self-contained, and written in natural language.
`goal` is optional and describes the broader end goal you are ultimately trying to accomplish on behalf of the user. GitBook uses it to tailor the answer towards what is most useful for that goal.

The response will contain a direct answer to the question and relevant excerpts and sources from the documentation.

Use this mechanism when the answer is not explicitly present in the current page, you need clarification or additional context, or you want to retrieve related documentation sections.
