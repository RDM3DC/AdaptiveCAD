#include "adaptivecad/Quaternion.h"
#include "adaptivecad/Matrix4.h"
#include <cmath>

namespace adaptivecad {

Quaternion Quaternion::from_axis_angle(const Vec3& axis, double angle_rad) {
    double half = angle_rad / 2.0;
    double s = std::sin(half);
    return Quaternion(std::cos(half), axis.x * s, axis.y * s, axis.z * s);
}

Quaternion Quaternion::conjugate() const {
    return Quaternion(w, -x, -y, -z);
}

Quaternion Quaternion::operator*(const Quaternion& other) const {
    return Quaternion(
        w * other.w - x * other.x - y * other.y - z * other.z,
        w * other.x + x * other.w + y * other.z - z * other.y,
        w * other.y - x * other.z + y * other.w + z * other.x,
        w * other.z + x * other.y - y * other.x + z * other.w);
}

Vec3 Quaternion::rotate(const Vec3& v) const {
    Quaternion qv(0.0, v.x, v.y, v.z);
    Quaternion qres = (*this) * qv * conjugate();
    return Vec3(qres.x, qres.y, qres.z);
}

Matrix4 Quaternion::to_matrix() const {
    return Matrix4::from_quaternion(*this);
}

} // namespace adaptivecad
