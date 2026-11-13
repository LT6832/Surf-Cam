
import time
import board
import adafruit_bmp3xx

# BMP388 detected at I2C address 0x77
i2c = board.I2C()
bmp = adafruit_bmp3xx.BMP3XX_I2C(i2c, address=0x77)

print("BMP388 barometer initialized!")

try:
    while True:
        print(
            f"Temperature: {bmp.temperature:.2f} °C | "
            f"Pressure: {bmp.pressure:.2f} hPa"
        )
        time.sleep(0.5)

except KeyboardInterrupt:
    print("\nStopped.")
