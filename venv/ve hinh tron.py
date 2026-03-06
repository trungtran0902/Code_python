import matplotlib.pyplot as plt
import numpy as np

# Bán kính của hình tròn
radius = 5

# Tạo dữ liệu cho hình tròn
theta = np.linspace(0, 2 * np.pi, 100)
x = radius * np.cos(theta)
y = radius * np.sin(theta)

# Vẽ hình tròn
plt.figure()
plt.plot(x, y)
plt.gca().set_aspect('equal', adjustable='box')
plt.title('Hình tròn')
plt.show()
