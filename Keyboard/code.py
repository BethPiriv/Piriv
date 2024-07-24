# Keyboard code. Includes lighting and a trackball
# huge thanks to David Boucher over on https://dboucher.org.uk/keyboard/
# and Hackaday for basically writing the actual code and explaining the
# process better than I ever could
# I pretty much just translated this into circuitpy
from adafruit_bus_device.i2c_device import I2CDevice
from adafruit_hid.mouse import Mouse
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keycode import Keycode

import usb_hid
import board
import busio
import digitalio
import neopixel

ledOn = False

led = digitalio.DigitalInOut(board.LED)
led.direction = digitalio.Direction.OUTPUT

I2C_ADDRESS = 0xA

REG_LED_RED = 0x00
REG_LED_GRN = 0x01
REG_LED_BLU = 0x02
REG_LED_WHT = 0x03

REG_LEFT = 0x04
REG_RIGHT = 0x05
REG_UP = 0x06
REG_DOWN = 0x07

# i2c @ address 0xA
m = Mouse(usb_hid.devices)
kbd = Keyboard(usb_hid.devices)
i2c = busio.I2C(board.GP21, board.GP20)
device = I2CDevice(i2c, I2C_ADDRESS)

# variables for operation ofmouse/keyboard
mSpeed = 7
mPressed = False
mReleased = False
debounceDelay = 3
holdDelay = 10
timeSinceKeyScan = 0

# backlighting stuff
# params = GPIO pin, Number of lights
pixels = neopixel.NeoPixel(board.GP19, 3)

# stores pressed keys each frame
pressedKeys = set()
# stores the current modifier
currentMod = 0
# stores which key forces right click
rClickMod = -2

# stores where in the set for each key your time
# pressed and keytype appears.
timePressed = 2
keyTypePos = 3

# stores which mouse button was pressed last
lastMouseButtonPressed = Mouse.LEFT_BUTTON

# no enums in circuitpy, so I'm just using ints for keytype
# 1 = printable, 2 = function, 3 = dead

# for keycodes, we can't use 0, as that's reserved, but
# for dead keys, -1
# for mod keys, -2 and below

# to reduce memory usage, we flip that value while finding which keys
# to press, e.g. -1 = 1, -2 = 2, that way, we can access
# the relevant keys from the set
# only works if you fill out the matrix with all the keypresses you need however
matrix_keys = [
    [
        (Keycode.Q, Keycode.POUND, 0, 1),
        (Keycode.W, Keycode.ONE, 0, 1),
        (Keycode.E, Keycode.TWO, 0, 1),
        (Keycode.R, Keycode.THREE, 0, 1),
        (Keycode.T, Keycode.NINE, 0, 1),
        (Keycode.Y, Keycode.ZERO, 0, 1),
        (Keycode.U, Keycode.MINUS, 0, 1),
        (Keycode.I, Keycode.MINUS, 0, 1),
        (Keycode.O, Keycode.EQUALS, 0, 1),
        (Keycode.P, Keycode.TWO, 0, 1),
    ],
    [
        (Keycode.A, Keycode.EIGHT, 0, 1),
        (Keycode.S, Keycode.FOUR, 0, 1),
        (Keycode.D, Keycode.FIVE, 0, 1),
        (Keycode.F, Keycode.SIX, 0, 1),
        (Keycode.G, Keycode.FORWARD_SLASH, 0, 1),
        (Keycode.H, Keycode.SEMICOLON, 0, 1),
        (Keycode.J, Keycode.SEMICOLON, 0, 1),
        (Keycode.K, Keycode.QUOTE, 0, 1),
        (Keycode.L, Keycode.QUOTE, 0, 1),
        (Keycode.BACKSPACE, Keycode.BACKSPACE, 0, 1),
    ],
    [
        (Keycode.ALT, Keycode.ALT, 0, 2),
        (Keycode.Z, Keycode.SEVEN, 0, 1),
        (Keycode.X, Keycode.EIGHT, 0, 1),
        (Keycode.C, Keycode.NINE, 0, 1),
        (Keycode.V, Keycode.FORWARD_SLASH, 0, 1),
        (Keycode.B, Keycode.ONE, 0, 1),
        (Keycode.N, Keycode.COMMA, 0, 1),
        (Keycode.M, Keycode.PERIOD, 0, 1),
        (Keycode.FOUR, Keycode.POUND, 0, 1),
        (Keycode.RETURN, Keycode.RETURN, 0, 1),
    ],
    [
        (-1, -1, 0, 3),
        (Keycode.SHIFT, Keycode.SHIFT, 0, 2),
        (-1, -1, 0, 3),
        (Keycode.CONTROL, Keycode.CONTROL, 0, 2),
        (Keycode.SPACEBAR, Keycode.SPACEBAR, 0, 1),
        (Keycode.SPACEBAR, Keycode.SPACEBAR, 0, 1),
        (-2, -2, 0, 2),
        (Keycode.SHIFT, Keycode.SHIFT, 0, 2),
        (-1, -1, 0, 3),
        (-1, -1, 0, 3),
    ],
]

# intensity of r,g,b,w LEDs from 0-100 e.g. set_leds(100,100,25,50)
def set_leds(r, g, b, w):
    device.write(bytes([REG_LED_RED, r & 0xFF]))
    device.write(bytes([REG_LED_GRN, g & 0xFF]))
    device.write(bytes([REG_LED_BLU, b & 0xFF]))
    device.write(bytes([REG_LED_WHT, w & 0xFF]))


def set_leds_purple():
    set_leds(60, 0, 90, 20)


def set_leds_orange():
    set_leds(99, 63, 8, 0)


def set_leds_yellow():
    set_leds(100, 85, 6, 0)


def set_leds_white():
    set_leds(0, 0, 0, 100)

# read trackball input
def i2c_rdwr(data, length=0):
    device.write(bytes(data))

    if length > 0:
        msg_r = bytearray(length)
        device.readinto(msg_r)
        return list(msg_r)
    return []


def read():
    # Read up, down, left, right and switch data from trackball
    left, right, up, down, switch = i2c_rdwr([REG_LEFT], 5)

    # this line resets the switch signal, so you can't hold it.
    # mechanically, may be a better idea to do this,
    # but I like to highlight stuff, so too bad
    # switch = 129 == switch
    return up, down, left, right, switch


col_pins = []
row_pins = []

# handy lil guide telling you where to solder your rows and columns
keypad_columns = [
    digitalio.DigitalInOut(board.GP6),
    digitalio.DigitalInOut(board.GP7),
    digitalio.DigitalInOut(board.GP8),
    digitalio.DigitalInOut(board.GP9),
    digitalio.DigitalInOut(board.GP10),
    digitalio.DigitalInOut(board.GP11),
    digitalio.DigitalInOut(board.GP12),
    digitalio.DigitalInOut(board.GP13),
    digitalio.DigitalInOut(board.GP14),
    digitalio.DigitalInOut(board.GP16),
]
keypad_rows = [
    digitalio.DigitalInOut(board.GP2),
    digitalio.DigitalInOut(board.GP3),
    digitalio.DigitalInOut(board.GP4),
    digitalio.DigitalInOut(board.GP5),
]

# we want the columns going in and pulling down,
# and the rows going out
def initPins():
    for x in range(0, 10):
        col_pins.append(keypad_columns[x])
        col_pins[x].direction = digitalio.Direction.INPUT
        col_pins[x].pull = digitalio.Pull.UP
    for x in range(0, 4):
        row_pins.append(keypad_rows[x])
        row_pins[x].direction = digitalio.Direction.OUTPUT
        row_pins[x].value = 0


# scan the mouse
def pollMouse():
    # let's see what that thang doing
    up, down, left, right, switch = read()

    # load up everything we're gonna change in this function
    global lUnclickedTime
    global mPressed
    global ledOn
    global mReleased
    global lastMouseButtonPressed

    # if we're getting a switch signal
    # (this code is only tested with the switch able to be held)
    # flag setting is so we don't spam left click button, or spam left click release.
    # this leaves it up to the OS as to what exactly the clicks do
    if switch:
        ledOn = True
        if not mPressed:

            mButton = Mouse.LEFT_BUTTON

            if currentMod == rClickMod:
                mButton = Mouse.RIGHT_BUTTON

            m.press(mButton)
            lastMouseButtonPressed = mButton
            mPressed = True
            mReleased = False
    else:
        if not mReleased:
            m.release(lastMouseButtonPressed)
            mPressed = False
            mReleased = True

    # gonna do some smoothing later, afaik, right and
    # left are per frame movements (sorry I say frame I'm a game dev)
    # so theoretically, I should be able to create a
    # target position, then move the mouse towards it
    # kinda what acceleration already does, but may as well build it in
    x = right - left
    y = down - up
    m.move(int(x * mSpeed), int(y * mSpeed), 0)

def scanKeys():
    global timeSinceKeyScan
    if timeSinceKeyScan < debounceDelay:
        timeSinceKeyScan += 1
        return

    timeSinceKeyScan = 0

    global ledOn
    global pressedKeys
    global repeatDelay

    for row in range(len(row_pins)):

        # set the row direction to output
        # set the value low
        row_pins[row].direction = digitalio.Direction.OUTPUT
        row_pins[row].value = 0

        for col in range(len(col_pins)):

            if matrix_keys[row][col][keyTypePos] == 3:
                continue

            keyVal = matrix_keys[row][col][0]
            keyValMod1 = matrix_keys[row][col][1]
            uptime = matrix_keys[row][col][timePressed]
            keyType = matrix_keys[row][col][keyTypePos]

            # make sure to reset all pins that aren't pressed
            if col_pins[col].value == 1:
                matrix_keys[row][col] = (keyVal, keyValMod1, 0, keyType)
                continue

            # next, lets cull anything that's been held,
            # but not long enough to start repeating
            if keyType == 1 and uptime < holdDelay and uptime > 0:
                matrix_keys[row][col] = (keyVal, keyValMod1, uptime + 1, keyType)
                continue

            ledOn = True
            # if it's a modifier key, let's send it to decide modifier
            # otherwise, let's add the co-ordinates to the keypress set
            if matrix_keys[row][col][0] < -1:
                decideModifier(matrix_keys[row][col][0])
            else:
                pressedKeys.add((row, col))

            # if it hasn't yet been held, start incrementing the timer
            if uptime < holdDelay and keyType != 2:
                matrix_keys[row][col] = (keyVal, keyValMod1, uptime + 1, keyType)

        # reset row pin output direction
        row_pins[row].direction = digitalio.Direction.INPUT

# we can have multiple modifiers pressed in any given frame,
# I'm deciding by last pressed, but you can decide by value,
# or write in a hierarchy as you wish
# e.g. if newMod < currentMod:
#           currentMod = newMod
def decideModifier(newMod):
    global currentMod
    currentMod = newMod


def flashLED():
    global ledOn
    led.value = ledOn
    ledOn = False

def applyLighting():
    # for now, just block colours, more to come
    pixels.fill((0, 255, 255, 0))
    pixels.show()


def pressKeys():
    global pressedKeys
    global currentMod

    keycodeSet = set()
    # only adjust the modifier if we've actually pressed one
    if currentMod != 0:
        currentMod = abs(currentMod) - 1

    for i in pressedKeys:
        row = i[0]
        col = i[1]
        keycodeSet.add(matrix_keys[row][col][currentMod])

    kbd.send(*keycodeSet)
    pressedKeys.clear()
    keycodeSet.clear()
    currentMod = 0


with device:

    set_leds_purple()
    initPins()

    while True:
        scanKeys()
        pollMouse()
        pressKeys()
        # lighting hurts my eyes rn, so I'm not bothering
        # I will get round to it, it's just not critical path
        # applyLighting()
        flashLED()
