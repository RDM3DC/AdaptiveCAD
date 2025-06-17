#ifndef ADAPTIVECAD_VEC3_H
#define ADAPTIVECAD_VEC3_H

namespace adaptivecad {

struct Vec3 {
    double x{0.0};
    double y{0.0};
    double z{0.0};

    Vec3() = default;
    Vec3(double x_, double y_, double z_) : x(x_), y(y_), z(z_) {}

    Vec3 operator+(const Vec3& other) const;
    Vec3 operator-(const Vec3& other) const;
    Vec3 operator*(double scalar) const;
    Vec3 operator/(double scalar) const;

    Vec3 cross(const Vec3& other) const;
    double dot(const Vec3& other) const;
    double norm() const;
    Vec3 normalize() const;
};

} // namespace adaptivecad

#endif // ADAPTIVECAD_VEC3_H
