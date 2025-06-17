#include "adaptivecad/Matrix4.h"
#include "adaptivecad/Quaternion.h"
#include <cmath>

namespace adaptivecad {

Matrix4::Matrix4() {
    for (int i = 0; i < 4; ++i) {
        for (int j = 0; j < 4; ++j) {
            m[i][j] = (i == j) ? 1.0 : 0.0;
        }
    }
}

Matrix4::Matrix4(const std::array<std::array<double,4>,4>& values) : m(values) {}

Matrix4 Matrix4::from_translation(const Vec3& offset) {
    Matrix4 mat;
    mat.m[0][3] = offset.x;
    mat.m[1][3] = offset.y;
    mat.m[2][3] = offset.z;
    return mat;
}

Matrix4 Matrix4::from_scale(double factor) {
    Matrix4 mat;
    mat.m[0][0] = mat.m[1][1] = mat.m[2][2] = factor;
    return mat;
}

Matrix4 Matrix4::from_scale(const Vec3& factor) {
    Matrix4 mat;
    mat.m[0][0] = factor.x;
    mat.m[1][1] = factor.y;
    mat.m[2][2] = factor.z;
    return mat;
}

Matrix4 Matrix4::from_quaternion(const Quaternion& q) {
    double x2 = q.x * 2;
    double y2 = q.y * 2;
    double z2 = q.z * 2;
    double wx = q.w * x2;
    double wy = q.w * y2;
    double wz = q.w * z2;
    double xx = q.x * x2;
    double xy = q.x * y2;
    double xz = q.x * z2;
    double yy = q.y * y2;
    double yz = q.y * z2;
    double zz = q.z * z2;
    Matrix4 mat;
    mat.m[0][0] = 1 - (yy + zz);
    mat.m[0][1] = xy - wz;
    mat.m[0][2] = xz + wy;
    mat.m[1][0] = xy + wz;
    mat.m[1][1] = 1 - (xx + zz);
    mat.m[1][2] = yz - wx;
    mat.m[2][0] = xz - wy;
    mat.m[2][1] = yz + wx;
    mat.m[2][2] = 1 - (xx + yy);
    return mat;
}

Matrix4 Matrix4::operator*(const Matrix4& other) const {
    Matrix4 result;
    for (int i = 0; i < 4; ++i) {
        for (int j = 0; j < 4; ++j) {
            result.m[i][j] = 0.0;
            for (int k = 0; k < 4; ++k) {
                result.m[i][j] += m[i][k] * other.m[k][j];
            }
        }
    }
    return result;
}

Vec3 Matrix4::transform_point(const Vec3& p) const {
    double x = m[0][0]*p.x + m[0][1]*p.y + m[0][2]*p.z + m[0][3];
    double y = m[1][0]*p.x + m[1][1]*p.y + m[1][2]*p.z + m[1][3];
    double z = m[2][0]*p.x + m[2][1]*p.y + m[2][2]*p.z + m[2][3];
    double w = m[3][0]*p.x + m[3][1]*p.y + m[3][2]*p.z + m[3][3];
    if (w != 0.0 && w != 1.0) {
        return Vec3(x/w, y/w, z/w);
    }
    return Vec3(x, y, z);
}

Vec3 Matrix4::transform_vector(const Vec3& v) const {
    double x = m[0][0]*v.x + m[0][1]*v.y + m[0][2]*v.z;
    double y = m[1][0]*v.x + m[1][1]*v.y + m[1][2]*v.z;
    double z = m[2][0]*v.x + m[2][1]*v.y + m[2][2]*v.z;
    return Vec3(x, y, z);
}

} // namespace adaptivecad
