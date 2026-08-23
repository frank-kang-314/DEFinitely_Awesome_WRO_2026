#include "Arduino_RouterBridge.h"

const int IN3 = 13;
const int IN4 = 12;
const int ENB = 11;

const int TRIG_FRONT = 8; const int ECHO_FRONT = 7;
const int TRIG_LEFT  = 3; const int ECHO_LEFT  = 2;
const int TRIG_RIGHT = 6; const int ECHO_RIGHT = 5;

const int SERVO_PIN = 10;

// Tune these to your servo — 1500 = straight, lower = right
const int PULSE_STRAIGHT = 1100; 
const int PULSE_RIGHT    = 1450;  

int currentPulseUs           = PULSE_STRAIGHT;
unsigned long lastPulseStart = 0;
bool pulseActive             = false;

void setServo(int pulseUs) {
  currentPulseUs = pulseUs;
}

void updateServo() {
  unsigned long now = micros();
  if (pulseActive) {
    if (now - lastPulseStart >= (unsigned long)currentPulseUs) {
      digitalWrite(SERVO_PIN, LOW);
      pulseActive = false;
    }
  } else {
    if (now - lastPulseStart >= 20000UL) {
      digitalWrite(SERVO_PIN, HIGH);
      lastPulseStart = now;
      pulseActive    = true;
    }
  }
}

long readCM(int trig, int echo) {
  digitalWrite(trig, LOW);  delayMicroseconds(2);
  digitalWrite(trig, HIGH); delayMicroseconds(10);
  digitalWrite(trig, LOW);
  unsigned long start = micros();
  while (digitalRead(echo) == LOW)  { updateServo(); if (micros() - start > 5000) return 999; }
  unsigned long pulseStart = micros();
  while (digitalRead(echo) == HIGH) { updateServo(); if (micros() - pulseStart > 5000) return 999; }
  long dur = micros() - pulseStart;
  return dur * 0.0343 / 2;
}

String get_data() {
  long front = readCM(TRIG_FRONT, ECHO_FRONT);
  long left  = readCM(TRIG_LEFT,  ECHO_LEFT);
  long right = readCM(TRIG_RIGHT, ECHO_RIGHT);
  return String(front) + "," + String(left) + "," + String(right);
}

String set_steering(String cmd) {
  cmd.trim();
  if (cmd == "RIGHT") setServo(PULSE_RIGHT);
  else                setServo(PULSE_STRAIGHT);
  return "OK:" + cmd;
}

void setup() {
  pinMode(IN3, OUTPUT); pinMode(IN4, OUTPUT); pinMode(ENB, OUTPUT);
  digitalWrite(IN3, LOW);
  digitalWrite(IN4, HIGH);
  digitalWrite(ENB, HIGH);

  pinMode(TRIG_FRONT, OUTPUT); pinMode(ECHO_FRONT, INPUT);
  pinMode(TRIG_LEFT,  OUTPUT); pinMode(ECHO_LEFT,  INPUT);
  pinMode(TRIG_RIGHT, OUTPUT); pinMode(ECHO_RIGHT, INPUT);

  pinMode(SERVO_PIN, OUTPUT);
  digitalWrite(SERVO_PIN, LOW);
  lastPulseStart = micros();

  Serial.begin(9600);
  Bridge.begin();
  Bridge.provide("get_data",     get_data);
  Bridge.provide("set_steering", set_steering);
}

void loop() {
  updateServo();
}