from __future__ import absolute_import, division, print_function

"""Functions to visualize human poses"""
import numpy as np
import h5py
import os
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.animation import FuncAnimation
from PIL import Image


class Ax3DPose(object):
    def __init__(self, ax, data_set, lcolor="#3498db", rcolor="#e74c3c"):
        """
        Create a 3d pose visualizer that can be updated with new poses.

        Args
          ax: 3d axis to plot the 3d pose on
          lcolor: String. Colour for the left part of the body
          rcolor: String. Colour for the right part of the body
        """

        if data_set == "NTURGBD":
            self.body_members = {
                'left_arm': {'joints': [20, 8, 9, 10, 11], 'side': 'left'},
                # [21, 9, 10, 11, 12, 24, 25]
                'right_arm': {'joints': [20, 4, 5, 6, 7], 'side': 'right'},
                # [21, 5, 6, 7, 8, 22, 23]
                'head': {'joints': [20, 2, 3], 'side': 'right'},
                'torso': {'joints': [20, 1, 0], 'side': 'right'},
                'left_leg': {'joints': [0, 16, 17, 18, 19], 'side': 'left'},
                'right_leg': {'joints': [0, 12, 13, 14, 15], 'side': 'right'},
            }
            self.njoints = 25
        elif data_set == "MSRC12":
            self.body_members = {
                'left_arm': {'joints': [2, 4, 5, 6, 7], 'side': 'left'},
                'right_arm': {'joints': [2, 8, 9, 10, 11], 'side': 'right'},
                'head': {'joints': [1, 2, 3], 'side': 'right'},
                'torso': {'joints': [1, 0], 'side': 'right'},
                'left_leg': {'joints': [0, 12, 13, 14, 15], 'side': 'left'},
                'right_leg': {'joints': [0, 16, 17, 18, 19], 'side': 'right'},
            }
            self.njoints = 20

        # Human3.6
        # self.body_members = {
        #   'left_arm': {'joints': [16, 17, 18, 19, 20, 21, 20, 19, 22, 23, 22, 19, 18, 17, 16, 12], 'side': 'left'},
        #   'right_arm': {'joints': [24, 25, 26, 27, 28, 29, 28, 27, 30, 31, 30, 27, 26, 25, 24, 12], 'side': 'right'},
        #   'head': {'joints': [13, 14, 15, 14, 13, 12], 'side': 'right'},
        #   'torso': {'joints': [0, 11, 12], 'side': 'right'},
        #   'left_leg': {'joints': [0, 6, 7, 8, 9, 10, 9, 8, 7, 6], 'side': 'left'},
        #   'right_leg': {'joints': [0, 1, 2, 3, 4, 5, 4, 3, 2, 1], 'side': 'right'},
        # }
        # self.njoints = 32

        # OpenPose
        # self.body_members = {
        #       'left_arm': {'joints': [2, 3, 4, 3, 2], 'side': 'left'},
        #       'right_arm': {'joints': [5, 6, 7, 6, 5], 'side': 'right'},
        #       'head': {'joints': [1, 0, 1], 'side': 'right'},
        #       # 'ext_head': {'joints': [14, 15, 16, 17, 16, 15, 14], 'side': 'right'},
        #       'ears': {'joints': [14, 0, 15], 'side': 'right'},
        #       'torso': {'joints': [2, 1, 5, 1, 8, 1, 11], 'side': 'right'},
        #       'left_leg': {'joints': [8, 9, 10, 9, 8], 'side': 'left'},
        #       'right_leg': {'joints': [11, 12, 13, 12, 11], 'side': 'right'},
        # }
        # self.njoints = 16

        self.ax = ax

        # Make connection matrix
        self.plots = {}
        for member in self.body_members.values():
            for j in range(len(member['joints']) - 1):
                j_idx_start = member['joints'][j]
                j_idx_end = member['joints'][j + 1]
                self.plots[(j_idx_start, j_idx_end)] = \
                    self.ax.plot([0, 0], [0, 0], [0, 0], lw=2, c=lcolor if member['side'] == 'left' else rcolor)

        self.plots_mask = []
        for j in range(self.njoints):
            self.plots_mask.append(
                self.ax.plot([0], [0], [0], lw=2, c='black', markersize=12, marker='o', linestyle='dashed', visible=False))

        self.ax.set_xlabel("x")
        self.ax.set_ylabel("y")
        self.ax.set_zlabel("z")

        self.axes_set = False

    def update(self, channels, mask=None):
        """
        Update the plotted 3d pose.

        Args
          channels: njoints * 3-dim long np array. The pose to plot.
          lcolor: String. Colour for the left part of the body.
          rcolor: String. Colour for the right part of the body.
        Returns
          Nothing. Simply updates the axis with the new pose.
        """

        assert channels.size == self.njoints * 3, \
            "channels should have %d entries, it has %d instead" % (self.njoints * 3, channels.size)
        vals = np.reshape(channels, (self.njoints, -1))

        for member in self.body_members.values():
            for j in range(len(member['joints']) - 1):
                j_idx_start = member['joints'][j]
                j_idx_end = member['joints'][j + 1]
                x = np.array([vals[j_idx_start, 0], vals[j_idx_end, 0]])
                y = np.array([vals[j_idx_start, 1], vals[j_idx_end, 1]])
                z = np.array([vals[j_idx_start, 2], vals[j_idx_end, 2]])
                self.plots[(j_idx_start, j_idx_end)][0].set_xdata(x)
                self.plots[(j_idx_start, j_idx_end)][0].set_ydata(y)
                self.plots[(j_idx_start, j_idx_end)][0].set_3d_properties(z)

        if mask is not None:
            for j in range(self.njoints):
                if mask[j] == 0:
                    self.plots_mask[j].set_visible(True)
                self.plots_mask[j].set_xdata(vals[j, 0])
                self.plots_mask[j].set_ydata(vals[j, 1])
                self.plots_mask[j].set_3d_properties(vals[j, 2])

        if not self.axes_set:
            r = 1  # 500;
            # xroot, yroot, zroot = vals[0, 0], vals[0, 1], vals[0, 2]
            xroot, yroot, zroot = 0, 0, vals[0, 2]
            self.ax.set_xlim3d([-r + xroot, r + xroot])
            self.ax.set_zlim3d([-r + zroot, r + zroot])
            self.ax.set_ylim3d([-r + yroot, r + yroot])

            self.ax.set_aspect('equal')
            self.axes_set = True

NTU_ACTIONS = ["drink water", "eat meal/snack", "brushing teeth",
               "brushing hair", "drop", "pickup", "throw", "sitting down",
               "standing up (from sitting position)", "clapping", "reading",
               "writing", "tear up paper", "wear jacket", "take off jacket",
               "wear a shoe", "take off a shoe", "wear on glasses",
               "take off glasses", "put on a hat/cap", "take off a hat/cap",
               "cheer up", "hand waving", "kicking something",
               "put something inside pocket / take out something from pocket",
               "hopping (one foot jumping)", "jump up",
               "make a phone call/answer phone", "playing with phone/tablet",
               "typing on a keyboard", "pointing to something with finger",
               "taking a selfie", "check time (from watch)",
               "rub two hands together", "nod head/bow", "shake head",
               "wipe face", "salute", "put the palms together",
               "cross hands in front (say stop)", "sneeze/cough", "staggering",
               "falling", "touch head (headache)",
               "touch chest (stomachache/heart pain)", "touch back (backache)",
               "touch neck (neckache)", "nausea or vomiting condition",
               "use a fan (with hand or paper)/feeling warm",
               "punching/slapping other person", "kicking other person",
               "pushing other person", "pat on back of other person",
               "point finger at the other person", "hugging other person",
               "giving something to other person",
               "touch other person's pocket", "handshaking",
               "walking towards each other", "walking apart from each other"]


MSRC_ACTIONS = ["Start system", "Duck", "Push right",
                "Googles", "Wind it up", "Shoot",
                "Bow", "Throw", "Had enough",
                "Change weapon", "Beat both", "Kick"]

def plot_gif(real_seq, gen_seq, labs, data_set, save_path=None, extra_text=None, seq_mask=None):
    import matplotlib
    if save_path is not None:
        matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    # === Plot and animate ===
    fig = plt.figure(dpi=80, figsize=plt.figaspect(1 / 2))

    if data_set == "NTURGBD":
        actions_l = NTU_ACTIONS
    elif data_set == "MSRC12":
        actions_l = MSRC_ACTIONS

    seq_idx, subject, action, plen = labs
    title = "action: %s  subject: %d  seq_idx: %d  length: %d" % \
              (actions_l[action], subject, seq_idx, plen)

    fig.suptitle(title)

    ax0 = fig.add_subplot(1, 2, 1, projection='3d')
    ax0.view_init(elev=90, azim=-90)
    # ax0.view_init(elev=0, azim=90)
    ob0 = Ax3DPose(ax0, data_set)

    ax1 = fig.add_subplot(1, 2, 2, projection='3d')
    ax1.view_init(elev=90, azim=-90)
    ob1 = Ax3DPose(ax1, data_set)

    seq_len = np.shape(real_seq)[1]
    frame_counter = fig.text(0.9, 0.1, 'frame: 0')
    if extra_text is not None:
        fig.text(0.1, 0.1, extra_text)

    def update(frame):
        mask = None
        if seq_mask is not None:
            mask = seq_mask[:, frame, 0]
        ob0.update(real_seq[:, frame, :], mask)
        ob1.update(gen_seq[:, frame, :])
        frame_counter.set_text('frame: %d' % frame)
        frame_counter.set_color('red' if frame > seq_len // 2 else 'blue')
        return ax0, ax1

    anim = FuncAnimation(fig, update, frames=np.arange(0, seq_len), interval=100)
    if save_path is not None:
        anim.save(save_path, dpi=80, writer='imagemagick')
    else:
        plt.show()

    fig_size = (int(fig.get_figheight()), int(fig.get_figwidth()))
    plt.close(fig)

    return fig_size


def plot_mult_gif(seqs, labs, data_set, save_path=None):
    import matplotlib
    if save_path is not None:
        matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    n_seqs = seqs.shape[0]
    n_rows = np.int(np.sqrt(n_seqs) * 9 / 16)
    n_cols = np.int(n_seqs / n_rows)
    # Note some seqs will not be displayed by rounding
    n_seqs = n_rows * n_cols

    my_dpi = 60
    fig = plt.figure(figsize=(1920 / my_dpi, 1080 / my_dpi), dpi=my_dpi)

    if data_set == "NTURGBD":
        actions_l = NTU_ACTIONS
    elif data_set == "MSRC12":
        actions_l = MSRC_ACTIONS

    axs = []
    obs = []
    for i in range(n_seqs):
        ax = fig.add_subplot(n_rows, n_cols, i + 1, projection='3d')
        ax.view_init(elev=90, azim=-90)
        # ax.view_init(elev=0, azim=90)
        ob = Ax3DPose(ax, data_set)
        axs.append(ax)
        obs.append(ob)

    seq_len = seqs.shape[2]
    frame_counter = fig.text(0.9, 0.1, 'frame: 0')

    def update(frame):
        for i in range(n_seqs):
            obs[i].update(seqs[i, :, frame, :])
            axs[i].set_xlabel('seq_idx: %d' % labs[i, 0])
        frame_counter.set_text('frame: %d' % frame)
        frame_counter.set_color('red' if frame > seq_len // 2 else 'blue')

    anim = FuncAnimation(fig, update, frames=np.arange(0, seq_len), interval=100)
    if save_path is not None:
        anim.save(save_path, dpi=80, writer='imagemagick')
    else:
        plt.show()

    fig_size = (int(fig.get_figheight()), int(fig.get_figwidth()))
    plt.close(fig)

    return fig_size


def plot_emb(seq_emb, save_path):
    seq_emb = (seq_emb - np.min(seq_emb)) / (np.max(seq_emb) - np.min(seq_emb))
    seq_emb = (seq_emb * 255).astype(np.uint8)
    im = Image.fromarray(seq_emb, mode='L')
    im.save(save_path)
