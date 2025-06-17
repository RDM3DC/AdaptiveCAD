#include "adaptivecad/Vec3.h"
#include <cmath>

namespace adaptivecad {

Vec3 Vec3::operator+(const Vec3& other) const {
    return Vec3(x + other.x, y + other.y, z + other.z);
}

Vec3 Vec3::operator-(const Vec3& other) const {
    return Vec3(x - other.x, y - other.y, z - other.z);
}

Vec3 Vec3::operator*(double scalar) const {
    return Vec3(x * scalar, y * scalar, z * scalar);
}

Vec3 Vec3::operator/(double scalar) const {
    return Vec3(x / scalar, y / scalar, z / scalar);
}

Vec3 Vec3::cross(const Vec3& other) const {
    return Vec3(
        y * other.z - z * other.y,
        z * other.x - x * other.z,
        x * other.y - y * other.x);
}

double Vec3::dot(const Vec3& other) const {
    return x * other.x + y * other.y + z * other.z;
}

double Vec3::norm() const {
    return std::sqrt(dot(*this));
}

Vec3 Vec3::normalize() const {
    double n = norm();
    if (n == 0.0) {
        return Vec3(0.0, 0.0, 0.0);
    }
    return (*this) / n;
}

} // namespace adaptivecad
