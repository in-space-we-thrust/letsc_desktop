# Пример для Калмана:
class KalmanFilter:
    def __init__(self, process_noise, measurement_noise):
        self.process_noise = process_noise
        self.measurement_noise = measurement_noise
        self.estimated_error = 1.0
        self.estimate = 0.0

    def apply(self, measurement):
        self.estimated_error += self.process_noise
        kalman_gain = self.estimated_error / (self.estimated_error + self.measurement_noise)
        self.estimate = self.estimate + kalman_gain * (measurement - self.estimate)
        self.estimated_error = (1 - kalman_gain) * self.estimated_error
        return self.estimate