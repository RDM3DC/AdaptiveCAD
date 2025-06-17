#ifndef ADAPTIVECAD_QUATERNION_H
#define ADAPTIVECAD_QUATERNION_H

#include "adaptivecad/Vec3.h"

namespace adaptivecad {

struct Matrix4; // forward declaration

struct Quaternion {
    double w{1.0};
    double x{0.0};
    double y{0.0};
    double z{0.0};

    Quaternion() = default;
    Quaternion(double w_, double x_, double y_, double z_)
        : w(w_), x(x_), y(y_), z(z_) {}

    static Quaternion from_axis_angle(const Vec3& axis, double angle_rad);
    Quaternion conjugate() const;
    Quaternion operator*(const Quaternion& other) const;
    Vec3 rotate(const Vec3& v) const;
    Matrix4 to_matrix() const;
};

} // namespace adaptivecad

#endif // ADAPTIVECAD_QUATERNION_H
