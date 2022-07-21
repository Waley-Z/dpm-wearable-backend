import numpy as np


class Fatigue:
    def __init__(self, username):
        self.username = username
        self.age = 30
        # will be determined individually. 26 is a sample number.
        self.HRR_CP = 26
        # will be determined individually based on linear regression between percieved WBF (survey) and W_exp calculated using HRR.
        self.W_total = 200
        # Minimum heart rate collected during resting session.
        self.Rest_HR = 40
        # Maximum heart rate calculation using age.
        self.Max_HR = 200 - 0.7 * self.age

        # This is a constant value that will be determined for individual subjects but the constant will be included in AWC_total. So we define k as 1.
        self.K = 1
        self.R = 1    # will be th e set 1 for the same reasons as k.

        self.W_exp_today = []

    def fatigue_assess(self, HR, Num_session, W_exp_init):

        # Heart rate reserve for each minute
        HRR = (HR - self.Rest_HR) / (self.Max_HR - self.Rest_HR) * 100

        len_ = len(HR)
        W_exp = np.zeros(len_)  # empty array to record W_exp for each minute

        # if Num_session == 0:
        #     W_exp_init = 0
        # else:
        #     W_exp_init = 5
        # # will be the value of W_expended one minute before.
        # For instance to calucate WBF at 9:31am, we need to use W_expended at 9:30am

        if HRR[0] > self.HRR_CP:
            W_exp[0] = W_exp_init + self.K * (HRR[0] - self.HRR_CP)

        else:
            W_exp[0] = W_exp_init

        for i in range(1, len_):
            if HRR[i] > self.HRR_CP:
                W_exp[i] = W_exp[i - 1] + self.K * (HRR[i] - self.HRR_CP)

            else:
                # W_exp cannot be below zero.
                W_exp[i] = max(W_exp[i - 1] - self.R * (self.HRR_CP - HRR[i]), 0)

        WBF = W_exp / self.W_total

        self.W_exp_today = np.append(self.W_exp_today, WBF)


def main():
    # (sample, 1) - HR value collected from E4.
    HR = np.random.rand(100, 1) * 100 + 50
    subject = 'John'
    num_session = 1  # 9:00 - 9:30 -> session 1, 9:30 - 10:00 -> session 2

    john = Fatigue(subject)
    john.fatigue_assess(HR, num_session, 0)

    print(john.W_exp_today)


if __name__ == '__main__':
    main()
