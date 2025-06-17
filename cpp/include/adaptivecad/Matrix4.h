#ifndef ADAPTIVECAD_MATRIX4_H
#define ADAPTIVECAD_MATRIX4_H

#include "adaptivecad/Vec3.h"
#include <array>

namespace adaptivecad {

struct Quaternion;

struct Matrix4 {
    // Column-major 4x4 matrix
    std::array<std::array<double,4>,4> m{};

    Matrix4();
    explicit Matrix4(const std::array<std::array<double,4>,4>& values);

    static Matrix4 from_translation(const Vec3& offset);
    static Matrix4 from_scale(double factor);
    static Matrix4 from_scale(const Vec3& factor);
    static Matrix4 from_quaternion(const Quaternion& q);

    Matrix4 operator*(const Matrix4& other) const;

    Vec3 transform_point(const Vec3& p) const;
    Vec3 transform_vector(const Vec3& v) const;
};

} // namespace adaptivecad

#endif // ADAPTIVECAD_MATRIX4_H
