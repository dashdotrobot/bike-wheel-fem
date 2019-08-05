'Core classes BicycleWheel, Hub, Rim, and Spoke'

import numpy as np
from warnings import warn


class Rim:
    'Rim definition.'

    def __init__(self, radius, area,
                 I_rad, I_lat, J_tor, I_warp,
                 young_mod, shear_mod, density=None,
                 sec_type='general', sec_params={}):
        self.radius = radius
        self.area = area
        self.I_rad = I_rad
        self.I_lat = I_lat
        self.J_tor = J_tor
        self.I_warp = I_warp
        self.young_mod = young_mod
        self.shear_mod = shear_mod
        self.density = density
        self.sec_type = sec_type
        self.sec_params = sec_params

    @classmethod
    def general(cls, radius, area,
                I_rad, I_lat, J_tor, I_warp,
                young_mod, shear_mod, density=None):
        'Define a rim with arbitrary section properties.'

        r = cls(radius=radius, area=area,
                I_rad=I_rad, I_lat=I_lat, J_tor=J_tor, I_warp=I_warp,
                young_mod=young_mod, shear_mod=shear_mod, density=density,
                sec_type='general', sec_params={})

        return r

    @classmethod
    def box(cls, radius, w, h, t, young_mod, shear_mod, density=None):
        """Define a rim from a box cross-section.

        Args:
            w: width of the rim cross-section, from midline to midline.
            h: height of the rim cross-section (radial direction).
            t: wall thickness."""

        area = 2*(w+t/2)*t + 2*(h-t/2)*t

        # Torsion constant
        J_tor = 2*t*(w*h)**2 / (w + h)

        # Moments of area
        I_rad = 2*(t*(h+t)**3)/12 + 2*((w-t)*t**3/12 + (w-t)*t*(h/2)**2)
        I_lat = 2*(t*(w+t)**3)/12 + 2*((h-t)*t**3/12 + (h-t)*t*(w/2)**2)

        # Warping constant, closed thin-walled section
        I_warp = I_warp

        r = cls(radius=radius, area=area,
                I_rad=I_rad, I_lat=I_lat, J_tor=J_tor, I_warp=I_warp,
                young_mod=young_mod, shear_mod=shear_mod, density=density,
                sec_type='box', sec_params={'closed': True,
                                            'w': w, 'h': h, 't': t})

        return r

    @classmethod
    def C_channel(cls, radius, w, h, t, young_mod, shear_mod, density=None):
        'Construct a rim from a C channel cross-section.'

        area = (w+t)*t + 2*(h-t)*t

        # Torsion and warping constants
        # homepage.tudelft.nl/p3r3s/b16_chap7.pdf

        J_tor = 1.0/3.0 * t**3 * (w + 2*(h-t))
        I_warp = (t*h**3*w**2/12) * (3*h + 2*w)/(6*h + w)

        # Moments of area -----------------------------
        # Centroid location
        y_c = (h-t)*t*h / area
        I_rad = (w+t)*t**3/12 + (w+t)*t*y_c**2 +\
            2 * (t*(h-t)**3/12 + (h-t)*t*(h/2 - y_c)**2)
        I_lat = (t*w**3)/12 + 2*(((h-t)*t**3)/12 + (h-t)*t*(w/2)**2)

        # Shear center --------------------------------
        y_s = -3*h**2/(6*h + w)

        r = cls(radius=radius, area=area,
                I_rad=I_rad, I_lat=I_lat, J_tor=J_tor, I_warp=I_warp,
                young_mod=young_mod, shear_mod=shear_mod, density=density,
                sec_type='C', sec_params={'closed': False,
                                          'w': w, 'h': h, 't': t,
                                          'y_c': y_c, 'y_s': y_s, 'y_0': y_c - y_s})

        return r

    def calc_mass(self):
        'Return the rim mass'

        if self.density is not None:
            return self.density * 2*np.pi*self.radius * self.area
        else:
            return None

    def calc_rot_inertia(self):
        'Return the rotational inertia about the axle'

        if self.density is not None:
            return self.calc_mass() * self.radius**2
        else:
            return None


class Hub:
    """Hub consisting of two parallel, circular flanges.

    Args:
        diameter_nds: diameter of the left-side hub flange.
        diameter_ds: diameter of the drive-side hub flange.
        width_nds: distance from rim plane to left-side flange.
        width_ds: distance from rim plane to drive-side flange.

    Usage:
        Symmetric:           Hub(diameter=0.05, width=0.05)
        Asymmetric, specify: Hub(diameter=0.05, width_nds=0.03, width_ds=0.02)
        Asymmetric, offset:  Hub(diameter_nds=0.04, diameter_ds=0.06, width=0.05, offset=0.01)
    """

    def __init__(self, diameter=None, diameter_nds=None, diameter_ds=None,
                 width=None, width_nds=None, width_ds=None, offset=None):

        # Set flange diameters
        self.diameter_nds = diameter
        self.diameter_ds = diameter

        if isinstance(diameter_nds, float):
            self.diameter_nds = diameter_nds
        if isinstance(diameter_ds, float):
            self.diameter_ds = diameter_ds

        # Set flange widths
        if isinstance(width, float):
            if offset is None:
                offset = 0.

            self.width_nds = width/2 + offset
            self.width_ds = width/2 - offset

            if (width_nds is not None) or (width_ds is not None):
                raise ValueError('Cannot specify width_left or width_right when using the offset parameter.')

        elif isinstance(width_nds, float) and isinstance(width_ds, float):
            self.width_nds = width_nds
            self.width_ds = width_ds
        else:
            raise ValueError('width_left and width_right must both be defined if not using the width parameter.')


class Spoke:
    """Spoke definition.

    Defines a single spoke based on the angular position on the rim, axial
    vector, spoke nipple offset vector, length, diameter, modulus, and density.

    The spoke does not know its own position in space because it doesn't know
    the radius of the rim. Thus it can only calculate local properties, like
    the stiffness matrix and rotational inertia about its own COM.
    """

    def calc_k(self, tension=True):
        """Calculate matrix relating force and moment at rim due to the
        spoke under a rim displacement (u,v,w) and rotation phi"""

        n = self.n                   # spoke vector
        e3 = np.array([0., 0., 1.])  # rim axial vector

        K_e = self.EA / self.length

        if tension:
            K_t = self.tension / self.length
        else:
            K_t = 0.

        k_f = K_e*np.outer(n, n) + K_t*(np.eye(3) - np.outer(n, n))

        # Change in force applied by spoke due to rim rotation, phi
        dFdphi = k_f.dot(np.cross(e3, self.b).reshape((3, 1)))

        # Change in torque applied by spoke due to rim rotation
        dTdphi = np.cross(self.b, e3).dot(k_f).dot(np.cross(self.b, e3))

        k = np.zeros((4, 4))

        k[0:3, 0:3] = k_f
        k[0:3, 3] = dFdphi.reshape((3))
        k[3, 0:3] = dFdphi.reshape(3)
        k[3, 3] = dTdphi

        return k

    def calc_k_geom(self):
        'Calculate the coefficient of the tension-dependent spoke stiffness matrix.'

        n = self.n
        e3 = np.array([0., 0., 1.])

        k_f = (1./self.length) * (np.eye(3) - np.outer(n, n))

        # Change in force applied by spoke due to rim rotation, phi
        dFdphi = k_f.dot(np.cross(e3, self.b).reshape((3, 1)))

        # Change in torque applied by spoke due to rim rotation
        dTdphi = np.cross(self.b, e3).dot(k_f).dot(np.cross(self.b, e3))

        k = np.zeros((4, 4))

        k[0:3, 0:3] = k_f
        k[0:3, 3] = dFdphi.reshape((3))
        k[3, 0:3] = dFdphi.reshape(3)
        k[3, 3] = dTdphi

        return k

    def calc_mass(self):
        'Return the spoke mass'

        if self.density is not None:
            return self.density * self.length * np.pi/4*self.diameter**2
        else:
            return None

    def calc_rot_inertia(self):
        'Return the spoke rotational inertia about its center-of-mass'

        if self.density is not None:
            return self.calc_mass()*(self.length*self.n[1])**2 / 12.
        else:
            return None

    def calc_tension_change(self, d, a=0.):
        'Calculate change in tension given d=(u,v,w,phi) and a tightening adjustment a'

        # Assume phi=0 if not given
        if len(d) < 4:
            d = np.append(d, 0.)

        # u_n = u_s + phi(e_3 x b)
        e3 = np.array([0., 0., 1.])
        un = np.array([d[0], d[1], d[2]]) + d[3]*np.cross(e3, self.b)

        return self.EA/self.length * (a - self.n.dot(un))

    def __init__(self, theta, n, b, length, diameter, young_mod, density=None):
        self.theta = theta    # Angular position of rim point
        self.n = np.array(n)  # Spoke axial unit vector
        self.b = np.array(b)  # Spoke nipple offset vector
        self.length = length
        self.diameter = diameter
        self.young_mod = young_mod
        self.density = density

        self.tension = 0.
        self.EA = np.pi / 4 * diameter**2 * young_mod



class BicycleWheel:
    """Bicycle wheel definition.

    Defines a bicycle wheel including geometry, spoke properties, and rim
    properties. Instances of the BicycleWheel class can be used as an input
    for theoretical calculations and FEM models.
    """


    def reorder_spokes(self):
        'Ensure that spokes are ordered according to theta_rim'

        a = np.argsort([s.theta for s in self.spokes])
        self.spokes = [self.spokes[i] for i in a]

    def lace_radial(self, n_spokes, diameter, young_mod, density=None, offset_lat=0., offset_rad=0.):
        'Add spokes in a radial spoke pattern.'

        return self.lace_cross(n_spokes, 0, diameter=diameter, young_mod=young_mod,
                               density=density, offset_lat=offset_lat, offset_rad=offset_rad)

    def lace_cross_side(self, n_spokes, n_cross, side=1, direction=1, offset=0, diameter=2.0e-3, young_mod=210e9, density=None, offset_lat=0., offset_rad=0.):
        'Generate cross-laced spokes from the rim to one hub flange.'

        # Direction (+1 leading, -1 trailing)
        direction = 2*(direction > 0) - 1

        # Side (+ non-drive-side, - drive-side)
        side = 1*(side > 0)

        # Hub parameters
        hub_z = [-self.hub_width_ds + offset_lat,
                 self.hub_width_nds - offset_lat]
        hub_r = [self.hub.diameter_ds, self.hub.diameter_nds]

        for s in range(n_spokes):
            
            theta_rim = 2*np.pi/n_spokes*s + offset
            theta_hub = theta_rim + 2*np.pi/n_spokes*n_cross*s_dir

            du = hub_z[side]
            dv = (self.rim.radius - offset_rad -
                  hub_r[side]*np.cos(theta_hub - theta_rim))
            dw = hub_r[side]*np.sin(theta_hub - theta_rim)

            dv = (self.rim.radius - offset_rad -
                  self.hub.diameter_ds/2*np.cos(theta_hub - theta_rim))
            dw = self.hub.diameter_ds/2*np.sin(theta_hub - theta_rim)

            length = np.sqrt(du**2 + dv**2 + dw**2)
            n = np.array([du/length, dv/length, dw/length])
            b = np.array([-offset, offset_rad, 0.])

            self.spokes.append(Spoke(theta_rim, n, b, length,
                                     diameter, young_mod, density=density))

            direction = 2*(direction < 0) - 1  # flip direction between +1 and -1

        self.reorder_spokes()
        return True

    def lace_cross(self, n_spokes, n_cross, diameter, young_mod, density=None, offset_lat=0., offset_rad=0.):
        'Generate spokes in a "cross" pattern with n_cross crossings.'

        # Remove any existing spokes
        self.spokes = []

        # Non-drive-side
        self.lace_cross_side(n_spokes//2, n_cross, side=1, direction=1, offset=0.,
                             diameter=diameter, young_mod=young_mod, density=density,
                             offset_lat=offset_lat, offset_rad=offset_rad)

        # Drive-side
        self.lace_cross_side(n_spokes//2, n_cross, side=1, direction=1, offset=np.pi/(n_spokes//2),
                             diameter=diameter, young_mod=young_mod, density=density,
                             offset_lat=offset_lat, offset_rad=offset_rad)

        return True

    def apply_tension(self, T_avg=None, T_left=None, T_right=None):
        'Apply tension to spokes based on average radial tension.'

        # Assume that there are only two tensions in the wheel: left and right
        # and that spokes alternate left, right, left, right...
        s_l = self.spokes[0]
        s_r = self.spokes[1]

        if T_avg is not None:  # Specify average radial tension
            T_l = 2 * T_avg * np.abs(s_r.n[0]) /\
                (np.abs(s_l.n[0]*s_r.n[1]) + np.abs(s_r.n[0]*s_l.n[1]))
            T_r = 2 * T_avg * np.abs(s_l.n[0]) /\
                (np.abs(s_l.n[0]*s_r.n[1]) + np.abs(s_r.n[0]*s_l.n[1]))

            for i in range(0, len(self.spokes), 2):
                self.spokes[i].tension = T_l

            for i in range(1, len(self.spokes), 2):
                self.spokes[i].tension = T_r

        elif T_right is not None:  # Specify right-side tension
            T_r = T_right
            T_l = np.abs(s_r.n[0]/s_l.n[0]) * T_right

        elif T_left is not None:  # Specify left-side tension
            T_l = T_left
            T_r = np.abs(s_l.n[0]/s_r.n[0]) * T_left

        else:
            raise TypeError('Must specify one of the following arguments: T_avg, T_left, or T_right.')

        # Apply tensions
        for i in range(0, len(self.spokes), 2):
            self.spokes[i].tension = T_l

        for i in range(1, len(self.spokes), 2):
            self.spokes[i].tension = T_r

    def calc_kbar(self, tension=True):
        'Calculate smeared-spoke stiffness matrix'

        k_bar = np.zeros((4, 4))

        for s in self.spokes:
            k_bar = k_bar + s.calc_k(tension=tension)/(2*np.pi*self.rim.radius)

        return k_bar

    def calc_kbar_geom(self):
        'Calculate smeared-spoke stiffness matrix, geometric component'

        k_bar = np.zeros((4, 4))

        # Get scaling factor for tension on each side of the wheel
        s_0 = self.spokes[0]
        s_1 = self.spokes[1]
        T_d = np.abs(s_0.n[0]*s_1.n[1]) + np.abs(s_1.n[0]*s_0.n[1])

        for s in self.spokes:
            k_bar = k_bar + \
                np.abs(s.n[0])/T_d * s.calc_k_geom()/(np.pi*self.rim.radius)

        return k_bar

    def calc_mass(self):
        'Calculate total mass of the wheel in kilograms.'

        m_rim = self.rim.calc_mass()
        if m_rim is None:
            m_rim = 0.
            warn('Rim density is not specified.')

        m_spokes = np.array([s.calc_mass() for s in self.spokes])
        if np.any(m_spokes == None):
            m_spokes = np.where(m_spokes == None, 0., m_spokes)
            warn('Some spoke densities are not specified.')

        return m_rim + np.sum(m_spokes)

    def calc_rot_inertia(self):
        'Calculate rotational inertia about the hub axle.'

        I_rim = self.rim.calc_rot_inertia()
        if I_rim is None:
            I_rim = 0.
            warn('Rim density is not specified.')

        I_spk = np.array([s.calc_rot_inertia() for s in self.spokes])
        if np.any(I_spk == None):
            I_spokes = 0.
            warn('Some spoke densities are not specified.')
        else:
            I_spokes = 0.
            for i, s in enumerate(self.spokes):
                rim_pt = np.array([0., -self.rim.radius + s.b[1], 0.])
                hub_pt = rim_pt + s.n*s.length
                mid_pt = 0.5*(rim_pt + hub_pt)
                mr2_spk = s.calc_mass()*(mid_pt[0]**2 + mid_pt[1]**2)
                I_spokes = I_spokes + I_spk[i] + mr2_spk

        return I_rim + I_spokes

    def __init__(self):
        self.spokes = []
        self.rim = None
        self.hub = None
