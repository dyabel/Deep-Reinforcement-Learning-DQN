
import numpy as np
import gym
import tensorflow as tf
import random
from collections import deque

class DQN():
    def __init__(self, gym_game, epsilon=1, epsilon_decay=0.995, epsilon_min=0.01, batch_size=32, discount_factor=0.9, num_of_episodes=500, with_dueling=True):
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay
        self.epsilon_min = epsilon_min
        self.batch_size = batch_size
        self.discount_factor = discount_factor
        self.num_of_episodes = num_of_episodes
        self.with_dueling = with_dueling
        self.game = gym_game
        self.environment = gym.make(gym_game)
        try:
            try:
                shape = self.environment.observation_space.shape
                self.state_size = (shape[0], shape[1], shape[2])
                self.s = shape[0]*shape[1]*shape[2]
                self.state_mode = "observation"
            except:
                self.state_size = self.environment.observation_space.shape[0]
                self.s = self.state_size
                self.state_mode = "information"
            self.state_container = "box"
        except:
            self.state_size = self.environment.observation_space.n
            self.state_mode = "information"
            self.state_container = "discrete"

        try:
            self.action_size = self.environment.action_space.shape[0]
        except:
            try:
                self.action_size = self.environment.action_space.n
            except:
                self.action_size = self.environment.action_space.shape[0]
        self.a = self.action_size

        print("state size is: ",self.state_size)
        print("action size is: ", self.action_size)
        self.memory = deque(maxlen=20000)
        self.priority = deque(maxlen=20000)
        self.model = self.create_model()
        self.sess = tf.InteractiveSession()
        self.sess.run(tf.global_variables_initializer())

    def create_model(self):
        """
        neural network model
        :return:
        """
        try:
            self.input = tf.placeholder(dtype=tf.float32, shape=(None, self.state_size[0], self.state_size[1], self.state_size[2]))
        except:
            if self.with_dueling:
                self.input = tf.placeholder(dtype=tf.float32, shape=(None, self.state_size, 1))
            else:
                self.input = tf.placeholder(dtype=tf.float32, shape=(None, self.state_size))

        self.target = tf.placeholder(dtype=tf.float32, shape=(None, self.action_size))
        self.importance = tf.placeholder(dtype=tf.float32, shape=(None))

        if not self.with_dueling:
            if self.state_mode == "information":
                # if the state is not an image)
                out = tf.nn.relu(self.noisy_dense(24, self.input))
                out = tf.nn.relu(self.noisy_dense(24, out))
                self.out = self.noisy_dense(self.action_size, out)
            elif self.state_mode == "observation":
                # if the state is an image
                out = tf.layers.conv2d(inputs=self.input, filters=128, kernel_size=(5,5), activation="relu")
                out = tf.layers.max_pooling2d(inputs=out,pool_size=(2,2),strides=(2,2))
                out = tf.layers.conv2d(inputs=self.input, filters=64, kernel_size=(3,3), activation="relu")
                out = tf.layers.max_pooling2d(inputs=out,pool_size=(2,2),strides=(2,2))
                out = tf.layers.flatten(inputs=out)
                out = tf.nn.relu(self.noisy_dense(64, out))
                out = tf.nn.relu(self.noisy_dense(64, out))
                self.out = self.noisy_dense(self.action_size, out)

        elif self.with_dueling:
            if self.state_mode == "information":
                # if the state is not an image

                out = tf.layers.conv1d(inputs=self.input, filters=8, kernel_size=2, padding="same", activation="relu")
                out = tf.layers.flatten(inputs=out)
                out = tf.nn.relu(self.noisy_dense(12, out))
                value = tf.nn.relu(self.noisy_dense(8, out))
                value = self.noisy_dense(1, value)

                advantage = tf.nn.relu(self.noisy_dense(8, out))
                advantage = tf.nn.relu(self.noisy_dense(self.action_size, advantage))
                advantage = tf.subtract(advantage,tf.reduce_mean(advantage, axis=1, keepdims=True))

                self.output = tf.add(value, advantage)

            elif self.state_mode == "observation":
                # if the state is an image
                out = tf.layers.conv2d(inputs=self.input, filters=128, kernel_size=(5,5), padding="same", activation="relu")
                out = tf.layers.max_pooling2d(inputs=out, pool_size=(2,2), strides=(2,2))
                out = tf.layers.conv2d(inputs=out, filters=64, kernel_size=(3,3), padding="same", activation="relu")
                out = tf.layers.max_pooling2d(inputs=out, pool_size=(2,2), strides=(2,2))
                out = tf.layers.flatten(inputs=out)
                out = tf.nn.relu(self.noisy_dense(64, out))
                value = tf.nn.relu(self.noisy_dense(64, out))
                value = self.noisy_dense(1, value)

                advantage = tf.nn.relu(self.noisy_dense(64, out))
                advantage = self.noisy_dense(self.action_size, advantage)
                advantage = tf.subtract(advantage,tf.reduce_mean(advantage, axis=1, keepdims=True))

                self.output = tf.add(value, advantage)


        loss = tf.reduce_mean(tf.multiply(tf.square(self.output - self.target),self.importance))
        self.optimizer = tf.train.AdamOptimizer().minimize(loss)
        return self.output

    def noisy_dense(self, units, input):
        """
        noisy dense layer
        :param units:
        :param input:
        :return:
        """
        w_shape = [units, input.shape[1].value]
        mu_w = tf.Variable(initial_value=tf.truncated_normal(shape=w_shape))
        sigma_w = tf.Variable(initial_value=tf.constant(0.017, shape=w_shape))
        epsilon_w = tf.random_uniform(shape=w_shape)

        b_shape = [units]
        mu_b = tf.Variable(initial_value=tf.truncated_normal(shape=b_shape))
        sigma_b = tf.Variable(initial_value=tf.constant(0.017, shape=b_shape))
        epsilon_b = tf.random_uniform(shape=b_shape)

        w = tf.add(mu_w, tf.multiply(sigma_w, epsilon_w))
        b = tf.add(mu_b, tf.multiply(sigma_b, epsilon_b))

        return tf.matmul(input, tf.transpose(w)) + b

    def predict(self, input, model):
        return self.sess.run(model, feed_dict={self.input: input})

    def fit(self, input, target, importance):
        self.sess.run(self.optimizer, feed_dict={self.input: input, self.target: target, self.importance: importance})

    def state_reshape(self, state):
        shape = state.shape
        if self.state_mode == "observation":
            return np.reshape(state, [1, shape[0], shape[1], shape[2]])
        elif self.state_mode == "information":
            if self.with_dueling:
                return np.reshape(state, [1, shape[0], 1])
            else:
                return np.reshape(state, [1, shape[0]])

    def act(self, state):
        """
        act randomly by probability of epsilon or predict the next move by the neural network model
        :param state:
        :return:
        """
        return np.argmax(self.predict(state, self.model)[0])

    def remember(self, state, next_state, action, reward, done):
        """
        remember the experience
        :param state:
        :param next_state:
        :param action:
        :param reward:
        :param done:
        :return:
        """
        self.prioritize(state, next_state, action, reward, done)

    def prioritize(self, state, next_state, action, reward, done, alpha=0.6):
        q_next = reward + self.discount_factor * self.predict(next_state, self.alternative_model)[0][np.argmax(self.predict(next_state, self.model)[0])]
        q = self.predict(state, self.model)[0][action]
        p = (np.abs(q_next-q)+ (np.e ** -10)) ** alpha
        self.priority.append(p)
        self.memory.append((state, next_state, action, reward, done))

    def get_priority_experience_batch(self):
        p_sum = np.sum(self.priority)
        prob = self.priority / p_sum
        sample_indices = random.choices(range(len(prob)), k=self.batch_size, weights=prob)
        importance = (1/prob) * (1/self.batch_size)
        importance = np.array(importance)[sample_indices]
        samples = np.array(self.memory)[sample_indices]
        return samples, importance

    def replay(self):
        """
        experience replay. find the q-value and train the neural network model with state as input and q-values as targets
        :return:
        """
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay
        batch, importance = self.get_priority_experience_batch()
        for b, i in zip(batch, importance):
            state, next_state, action, reward, done = b
            target = reward
            if not done:
                target = reward + self.discount_factor * self.predict(next_state, self.alternative_model)[0][np.argmax(self.predict(next_state, self.model)[0])]
            final_target = self.predict(state, self.model)
            final_target[0][action] = target
            imp = i ** (1-self.epsilon)
            imp = np.reshape(imp, 1)
            self.fit(state, final_target, imp)

    def play(self):
        """
        play for num_of_episodes. remember the experiences in each episode. replay the experience at the end of the episode
        :return:
        """
        for episode in range(self.num_of_episodes+1):
            state = self.environment.reset()
            state = self.state_reshape(state)
            self.alternative_model = self.model
            r = []
            t = 0
            while True:
                action = self.act(state)
                next_state, reward, done, _ = self.environment.step(action)
                next_state = self.state_reshape(next_state)
                self.remember(state, next_state, action, reward, done)
                state = next_state
                r.append(reward)
                t += 1
                if done:
                    r = np.mean(r)
                    print("episode number: ", episode,", reward: ",r , "time score: ", t)
                    self.save_info(episode, r, t)
                    break
            self.replay()

    def save_info(self, episode, reward, time):
        if self.with_dueling:
            file = open("./Plot/NoisyDuelingDoubleDQNwPER-"+self.game+"-"+str(self.num_of_episodes)+"-episodes-batchsize-"+str(self.batch_size), 'a')
        else:
            file = open("./Plot/NoisyDoubleDQNwPER-"+self.game+"-"+str(self.num_of_episodes)+"-episodes-batchsize-"+str(self.batch_size), 'a')
        file.write(str(episode)+" "+str(reward)+" "+str(time)+" \n")
        file.close()


game = "Pong-v0" # bd
# game = "CartPole-v1" # bd
dqn = DQN(game, num_of_episodes=5000, with_dueling = True)
dqn.play()
