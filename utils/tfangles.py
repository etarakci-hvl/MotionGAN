from __future__ import absolute_import, division, print_function
import tensorflow as tf
import numpy as np


def vector3d_to_quaternion(x):
    """Convert a tensor of 3D vectors to a quaternion.
    Prepends a 0 to the last dimension, i.e. [[1,2,3]] -> [[0,1,2,3]].
    Args:
        x: A `tf.Tensor` of rank R, the last dimension must be 3.
    Returns:
        A `Quaternion` of Rank R with the last dimension being 4.
    Raises:
        ValueError, if the last dimension of x is not 3.
    """
    x = tf.convert_to_tensor(x)
    if x.shape[-1] != 3:
        raise ValueError("The last dimension of x must be 3.")
    return tf.pad(x, (len(x.shape) - 1) * [[0, 0]] + [[1, 0]])


def quaternion_to_vector3d(q):
    """Remove the w component(s) of quaternion(s) q."""
    return q[..., 1:]


def rotate_vector_by_quaternion(q, v, q_ndims=None, v_ndims=None):
    """Rotate a vector (or tensor with last dimension of 3) by q.
    This function computes v' = q * v * conjugate(q) but faster.
    Fast version can be found here:
    https://blog.molecular-matters.com/2013/05/24/a-faster-quaternion-vector-multiplication/
    https://github.com/PhilJd/tf-quaternion/blob/master/tfquaternion/tfquaternion.py
    Args:
        q: A `tf.Tensor` with shape (..., 4)
        v: A `tf.Tensor` with shape (..., 3)
        q_ndims: The number of dimensions of q. Only necessary to specify if
            the shape of q is unknown.
        v_ndims: The number of dimensions of v. Only necessary to specify if
            the shape of v is unknown.
    Returns: A `tf.Tensor` with the broadcasted shape of v and q.
    """
    qnorm = tf.sqrt(tf.reduce_sum(tf.square(q), axis=-1, keep_dims=True) + 1e-8)
    q = q / qnorm
    w = q[..., 0]
    q_xyz = q[..., 1:]
    if q_xyz.shape.ndims is not None:
        q_ndims = q_xyz.shape.ndims
    if v.shape.ndims is not None:
        v_ndims = v.shape.ndims
    for _ in range(v_ndims - q_ndims):
        q_xyz = tf.expand_dims(q_xyz, axis=0)
    for _ in range(q_ndims - v_ndims):
        v = tf.expand_dims(v, axis=0) + tf.zeros_like(q_xyz)
    q_xyz += tf.zeros_like(v)
    v += tf.zeros_like(q_xyz)
    t = 2 * tf.cross(q_xyz, v)
    return v + tf.expand_dims(w, axis=-1) * t + tf.cross(q_xyz, t)


def quaternion_conjugate(q):
    """Compute the conjugate of q, i.e. [q.w, -q.x, -q.y, -q.z]."""
    return tf.multiply(q, [1.0, -1.0, -1.0, -1.0])


def quaternion_between(u, v):
    """Finds the quaternion between two tensor of 3D vectors.

    Args:
        u: A `tf.Tensor` of rank R, the last dimension must be 3.
        v: A `tf.Tensor` of rank R, the last dimension must be 3.

    Returns:
        A `Quaternion` of Rank R with the last dimension being 4.
        returns 1, 0, 0, 0 quaternion if either u or v is 0, 0, 0

    Raises:
        ValueError, if the last dimension of u and v is not 3.
    """
    #TODO: FIX stack operations and test code
    u = tf.convert_to_tensor(u)
    v = tf.convert_to_tensor(v)
    if u.shape[-1] != 3 or v.shape[-1] != 3:
        raise ValueError("The last dimension of u and v must be 3.")

    if u.shape != v.shape:
        raise ValueError("u and v must have the same shape")

    base_shape = [int(d) for d in u.shape]
    base_shape[-1] = 1
    zero_dim = tf.zeros(base_shape)
    one_dim = tf.ones(base_shape)

    def _batch_dot(a, b):
        return tf.reduce_sum(tf.multiply(a, b), axis=-1, keep_dims=True)

    def _length_2(a):
        return tf.reduce_sum(tf.square(a), axis=-1, keep_dims=True)

    def _normalize(a):
        return a / tf.sqrt(_length_2(a) + 1e-8)

    def _perpendicular_vector(a):
        """ Finds an arbitrary perpendicular vector to *a*.
            returns 0, 0, 0 for the all zeros singular case
        """

        return tf.where(
            tf.reduce_sum(a, axis=-1, keepdims=True) == 0.0, a,
            tf.where(
                tf.expand_dims(tf.where(a[..., 0]), axis=-1) == 0.0,
                tf.stack([one_dim, zero_dim, zero_dim]),
                tf.where(
                    tf.expand_dims(tf.where(a[..., 1]), axis=-1) == 0.0,
                    tf.stack([zero_dim, one_dim, zero_dim]),
                    tf.where(
                        tf.expand_dims(tf.where(a[..., 2]), axis=-1) == 0.0,
                        tf.stack([zero_dim, zero_dim, one_dim]),
                        tf.stack([one_dim, one_dim,
                                  -1.0 * tf.reduce_sum(u[..., :2], axis=-1, keepdims=True) / u[..., 2]], axis=-1)
                    )
                )
            )
        )

    # w = tf.dot(u, v) + sqrt(length_2(u) * length_2(v))
    # xyz = cross(u, v)

    k_cos_theta = _batch_dot(u, v)
    k = tf.sqrt(_length_2(u) * _length_2(v))

    return tf.where(
            tf.reduce_sum(u, axis=-1, keepdims=True) == 0.0, tf.stack([one_dim, u], axis=-1),
            tf.where(
                tf.reduce_sum(v, axis=-1, keepdims=True) == 0.0, tf.stack([one_dim, v], axis=-1),
                tf.where(
                    (k_cos_theta / k) == -1,
                    tf.stack([zero_dim, _normalize(_perpendicular_vector(u))], axis=-1),
                    _normalize(tf.stack([k_cos_theta + k, tf.cross(u, v)], axis=-1))
                )
            )

        )


def quat_to_expmap(q):
    """Converts a quaternion to an exponential map
    Tensorflow port and tensorization of code in:
    https://github.com/una-dinosauria/human-motion-prediction/blob/master/src/data_utils.py
    Args:
        q: 1x4 quaternion
    Returns:
        r: 1x3 exponential map
    Raises:
        ValueError if the l2 norm of the quaternion is not close to 1
    """
    # if (np.abs(np.linalg.norm(q)-1)>1e-3):
    # raise(ValueError, "quat2expmap: input quaternion is not norm 1")
    # TODO: test code

    sinhalftheta = tf.sqrt(tf.reduce_sum(tf.square(q[..., 1:]), axis=-1, keep_dims=True) + 1e-8)
    coshalftheta = q[..., 0]

    r0 = q[..., 1:] / sinhalftheta
    theta = 2 * tf.atan2(sinhalftheta, coshalftheta)
    theta = tf.mod(theta + 2*np.pi, 2*np.pi)

    theta = tf.where(theta > np.pi, 2 * np.pi - theta, theta)
    r0 = tf.where(theta > np.pi, -r0, r0)
    r = r0 * theta

    return r


def rotmat_to_quat(R):
    """
    Converts a rotation matrix to a quaternion
    Tensorflow port and tensorization of code in:
    https://github.com/una-dinosauria/human-motion-prediction/blob/master/src/data_utils.py
    Args:
      R: 3x3 rotation matrix
    Returns:
      q: 1x4 quaternion
    """
    # TODO: FIX stack operations and test code
    trans_dims = range(len(R.shape))
    trans_dims[-1], trans_dims[-2] = trans_dims[-2], trans_dims[-1]
    rotdiff = R - tf.transpose(R, trans_dims)

    r = tf.stack([-rotdiff[..., 1, 2], rotdiff[..., 0, 2], -rotdiff[..., 0, 1]], axis=-1)
    rnorm = tf.sqrt(tf.reduce_sum(tf.square(r), axis=-1, keep_dims=True) + 1e-8)
    sintheta = rnorm / 2.0
    r0 = r / rnorm

    costheta = (tf.trace(R) - 1.0) / 2.0

    theta = tf.atan2(sintheta, costheta)

    q = tf.stack([tf.cos(theta / 2),  r0 * tf.sin(theta / 2)], axis=-1)

    return q


def rotmat_to_expmap(R):
    return quat_to_expmap(rotmat_to_quat(R))


def expmap_to_rotmat(r):
    """
    Converts an exponential map angle to a rotation matrix
    Tensorflow port and tensorization of code in:
    https://github.com/una-dinosauria/human-motion-prediction/blob/master/src/data_utils.py
    Args:
      r: 1x3 exponential map
    Returns:
      R: 3x3 rotation matrix
    """
    # TODO: FIX stack operations and test code
    base_shape = [int(d) for d in r.shape]
    base_shape[-1] = 1
    zero_dim = tf.zeros(base_shape)

    theta = tf.sqrt(tf.reduce_sum(tf.square(r), axis=-1, keep_dims=True) + 1e-8)
    r0 = r / theta

    r0x = tf.reshape(
        tf.stack([zero_dim, -1.0 * r0[..., 2], r0[..., 1],
                  zero_dim, zero_dim, -1.0 * r0[..., 0],
                  zero_dim, zero_dim, zero_dim], axis=-1),
        base_shape[:-2] + [3, 3]
    )

    trans_dims = range(len(r.shape))
    trans_dims[-1], trans_dims[-2] = trans_dims[-2], trans_dims[-1]

    r0x = r0x - tf.transpose(r0x, trans_dims)
    tile_eye = tf.constant(np.tile(np.eye(3), base_shape[:-2] + [1, 1]))

    R = tile_eye + tf.sin(theta) * r0x + (1.0 - tf.cos(theta)) * \
        tf.reduce_sum(tf.multiply(r0x, r0x), axis=-1, keep_dims=True)
    return R


def quat_to_rotmat(q):
    """Calculate the corresponding rotation matrix.
    See
    http://www.euclideanspace.com/maths/geometry/rotations/conversions/quaternionToMatrix/
    https://github.com/PhilJd/tf-quaternion/blob/master/tfquaternion/tfquaternion.py
    Args:
        q: a (...x, 4) quaternion tensor
    Returns:
        A `tf.Tensor` with R+1 dimensions and
        shape [d_1, ..., d_(R-1), 3, 3], the rotation matrix
    """

    # helper functions
    def diag(a, b):  # computes the diagonal entries,  1 - 2*a**2 - 2*b**2
        return 1 - 2 * tf.pow(a, 2) - 2 * tf.pow(b, 2)

    def tr_add(a, b, c, d):  # computes triangle entries with addition
        return 2 * a * b + 2 * c * d

    def tr_sub(a, b, c, d):  # computes triangle entries with subtraction
        return 2 * a * b - 2 * c * d

    qnorm = tf.sqrt(tf.reduce_sum(tf.square(q), axis=-1, keep_dims=True) + 1e-8)
    w, x, y, z = tf.unstack(q / qnorm, axis=-1)
    m = [[diag(y, z), tr_sub(x, y, z, w), tr_add(x, z, y, w)],
         [tr_add(x, y, z, w), diag(x, z), tr_sub(y, z, x, w)],
         [tr_sub(x, z, y, w), tr_add(y, z, x, w), diag(x, y)]]
    return tf.stack([tf.stack(m[i], axis=-1) for i in range(3)], axis=-2)


def rotmat_to_euler(R):
    """
    Converts a rotation matrix to Euler angles
    Tensorflow port and tensorization of code in:
    https://github.com/una-dinosauria/human-motion-prediction/blob/master/src/data_utils.py
    Args:
      R: a 3x3 rotation matrix
    Returns:
      eul: a 3x1 Euler angle representation of R
    """
    # TODO: FIX stack operations and test codes
    base_shape = [int(d) for d in R.shape][:-1]
    base_shape[-1] = 1
    zero_dim = tf.zeros(base_shape)
    one_dim = tf.ones(base_shape)

    econd0 = R[..., 0, 2] == 1
    econd1 = R[..., 0, 2] == -1
    econd = tf.logical_or(econd0, econd1)

    E2 = tf.where(
        econd,
        tf.where(econd1, one_dim * np.pi / 2.0, one_dim * -np.pi / 2.0),
        -tf.asin(R[..., 0, 2])
    )
    E1 = tf.where(
        econd,
        tf.atan2(R[..., 1, 2], R[..., 0, 2]),
        tf.atan2(R[..., 1, 2] / tf.cos(E2), R[..., 2, 2] / tf.cos(E2))
    )
    E3 = tf.where(
        econd,
        zero_dim,
        tf.atan2(R[..., 0, 1] / tf.cos(E2), R[..., 0, 0] / tf.cos(E2))
    )

    eul = tf.expand_dims(tf.stack([E1, E2, E3], axis=-1), axis=-1)
    return eul