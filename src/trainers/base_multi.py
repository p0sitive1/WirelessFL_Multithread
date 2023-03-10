import os
from os.path import join 
import numpy as np
import torch
import time
from torch import Tensor
from src.models.client import Client
from src.utils.file_utils import convert_dict_2_json, convert_json_2_dict
from src.utils.log_utils import get_name
import src.communication.comm_config as connConfig
from threading import Thread
import threading
# import matlab.engine

class BaseTrainer(object):
    def __init__(self, options, trainerConfig):

        self.worker = trainerConfig['worker']

        self.pathOfGradient = get_name(options, name_type='grad')
        self.gpu = options['gpu']
        self.batch_size = options['batch_size']
        self.is_sys_heter = options['is_sys_heter']
        self.all_train_data_num = trainerConfig['all_train_data_num']
        self.clients = trainerConfig['clients']
        self.socketServer = trainerConfig['socketServer']
        self.debug = trainerConfig['debug']
        self.numOfClients = options['num_clients']
        self.without_rp = options['without_rp']
        self.c0 = options['c0']
        self.decay = options['decay']

        print('>>> Initialize {} clients in total'.format(len(self.clients)))

        self.num_round = options['num_round']
        self.clients_per_round = options['clients_per_round']
        self.eval_every = options['eval_every']
        self.simple_average = not options['noaverage']
        if 'proposed' in options['algo']:
            self.eng= matlab.engine.start_matlab()

        self.latest_model = self.worker.get_flat_model_params().detach()
        
        # Add time heterogeneity
        self.client_times = trainerConfig['client_times']
        # self.update_fre = options['update_fre']
        
        ## Load Gradient info if exist
        try:
            self.grad_clients = convert_json_2_dict(self.pathOfGradient, "cache/grad")
        except:
            self.grad_clients = None 

        
        
        # Info used 
        self.file_name = get_name(options, name_type='log')

        cpath = os.getcwd()

        self.file_path = join(cpath, 'log', options['experiment_folder'])

        num_sample_clients = [len(c.train_data) for c in self.clients]
        pk_clients = np.array(num_sample_clients) / np.sum(num_sample_clients)
        
        for i, c in enumerate(self.clients):
            c.pk = pk_clients[i]

        self.logExperimentInfo = {
            'info': options,
            'pk': pk_clients.tolist(),
            'gk': [],
            'qk': [],
            'acc': [],
            'global_loss': [],
            'round_time': [],
            'selected_clients': [],
            'sel_clients' : [],
            'round_client_times': [],
            'client_times': self.client_times.tolist(),
        }

        self.log_round_time = 0



    # get qk using matlab
    def get_qk_matlab(self, A, B, caller='bs1'):
        # LOWER_BOUND = 1e-7
        # UPPER_BOUND = 1-1e-7
        # N = self.numOfClients
        # A = matlab.double([x for x in A])
        # B = matlab.double([x for x in B])
        # C = matlab.double([self.c0])
        # Aeq = matlab.double([1]*N)
        # if caller != 'bs3':
        #     lb = matlab.double([LOWER_BOUND]*N)
        #     ub = matlab.double([UPPER_BOUND]*N)
        #     x0 = matlab.double([1/N]*N)
        # else:
        #     lb = []
        #     ub = []
        #     for c in self.clients:
        #         if not(c in self.selected_clients):
        #             # print(type(c.qk))
        #             lb.append(c.qk)
        #             ub.append(c.qk)
        #         else:
        #             lb.append(LOWER_BOUND)
        #             ub.append(UPPER_BOUND)
        #     lb = matlab.double(lb)
        #     ub = matlab.double(ub)
        #     x0 = matlab.double([x for x in self.prob])

        # ret = self.eng.m_fmincon_30(A,B,C,x0,Aeq,lb,ub)
        # return np.array(ret).squeeze()
        return np.array([0])

    def select_clients_with_prob_without_replacement(self, seed=1):
        num_clients = min(self.clients_per_round, len(self.clients))
        np.random.seed(seed)
        index = np.random.choice(len(self.clients), num_clients,replace=False, p=self.prob)
        index = sorted(index.tolist())

        select_clients = []
        select_index = []
        repeated_times = []
        for i in index:
            if i not in select_index:
                select_clients.append(self.clients[i])
                select_index.append(i)
                repeated_times.append(1)
            else:
                repeated_times[-1] += 1
        # check
        print("check",select_index == [c.cid for c in select_clients])
        return select_clients, repeated_times

    def get_real_time(self, stats):
        tcommOfClients = [stat['tcomm'] for stat in stats]
        return max(tcommOfClients) 

    def save_log(self, ):

        if not os.path.exists(self.file_path):
            os.makedirs(self.file_path)

        convert_dict_2_json(self.logExperimentInfo, self.file_name, self.file_path)

  
    def end_train(self, ):
        for i, c in enumerate(self.clients):
            info = self.socketServer.send_msg(
                message={
                    'type': connConfig.MSG_END_EXPERIMENT,
                    'msg': None,
                    'tag': '',
                },
                reciver={
                    'type': connConfig.CLIENT,
                    'num': c.cid,
                })
            if self.debug:
                print("size {}, time {}, speed {} byte/s".format(info['size'], info['time'], info['size']/info['time']))


    def move_model_to_gpu(model, options):
        if 'gpu' in options and (options['gpu'] is True):
            device = 0 if 'device' not in options else options['device']
            torch.cuda.set_device(device)
            torch.backends.cudnn.enabled = True
            model.cuda()
            print('>>> Use gpu on device {}'.format(device))
        else:
            print('>>> Don not use gpu')

   
    def train(self):
        raise NotImplementedError

    def select_clients(self, seed=1):
        """Selects num_clients clients 

        Args:
            1. seed: random seed
            2. num_clients: number of clients to select; default 20
                note that within function, num_clients is set to min(num_clients, len(possible_clients))

        Return:
            list of selected clients objects
        """
        num_clients = min(self.clients_per_round, len(self.clients))
        np.random.seed(seed)
        return np.random.choice(self.clients, num_clients, replace=False).tolist()

    def local_train(self, round_i, selected_clients):
        

        self.colns = []  # client solutions
        self.stats = []  # Client comp and comm costs

        # lr = self.worker.optimizer.get_current_lr()
        lr = 0.01

        # Step one: send selection signal & latest model 
        threads = list()
        for i, c in enumerate(selected_clients):
            thread = Thread(target=self.handle_train, args=(c, round_i, lr))
            thread.setDaemon(True)
            thread.start()
            threads.append(thread)
        
        for t in threads:
            t.join()
        
        # print(f"return {threading.current_thread()}")
        return self.colns, self.stats

    def handle_train(self, c, round_i, lr):
        self.send_model(c, round_i, lr)
        self.recv_model(c, round_i, lr)
    
    def send_model(self, c, round_i, lr):
        # print(f"sending model to {c} on thread {threading.current_thread()}")
        info = self.socketServer.send_msg(
            message={                'type': connConfig.MSG_LOCAL_TRAIN,
                'msg': {
                    'latest_model_list': self.latest_model.tolist(),
                    'lr': lr,
                    'round_i': round_i,
                },
                'tag': '',
            },
            reciver={
                'type': connConfig.CLIENT,
                'num': c.cid,
            })
        if self.debug:
            print("size {}, time {}, speed {} byte/s".format(info['size'], info['time'], info['size']/info['time']))
            

    def recv_model(self, c, round_i, lr):
        # print(f"receiving model from {c} on thread {threading.current_thread()}")
        self.socketServer.send_signal(connConfig.FIRST_SHAKE_HANDS,{'type':connConfig.CLIENT,'num':c.cid })
        message, info = self.socketServer.recv_msg({'type':connConfig.CLIENT,'num':c.cid })
        if self.debug:
            print("size {}, time {}, speed {} byte/s".format(info['size'], info['time'], info['size']/info['time']))

        msg = message['msg']
        soln = (msg['data_size'], Tensor(msg['local_solution_list']))
        stat = {
            'client': c.cid,
            'tcomp': msg['t_comp'],
            'tcomm': info['time'],
            'vcomm': info['size']/info['time'],
            'loss': msg['local_loss'],
            'acc': msg['local_acc']
        }

        print(">>>>>>>> Round {} | CID: {} loss: {:.5f}, acc: {:.5f}, t_comm: {:.5f}, t_comp: {:.5f}".format(round_i, c.cid, stat['loss'], stat['acc'], stat['tcomm'], stat['tcomp']))

        self.colns.append(soln)
        self.stats.append(stat)

    def get_grad(self, c):
        info = self.socketServer.send_msg(
            message={
                'type': connConfig.MSG_GET_GRAD,
                'msg': {
                    'latest_model_list': self.latest_model.tolist()
                },
                'tag': ''
            }, 
            reciver={
                'type': connConfig.CLIENT,
                'num': c.cid
            }
        )
        if self.debug:
            print("size {}, time {}, speed {} byte/s".format(info['size'], info['time'], info['size']/info['time']))

        message, info = self.socketServer.recv_msg(         
            sender={'type': connConfig.CLIENT,'num': c.cid}
        )

        msg = message['msg']

        if self.debug:
            print("size {}, time {}, speed {} byte/s".format(info['size'], info['time'], info['size']/info['time']))
        
        return msg['c_grad']


    def aggregate(self, colns, **kwargs):
        """Aggregate local solutions and output new global parameter

        Args:
            colns: a generator or (list) with element (num_sample, local_solution)

        Returns:
            flat global model parameter
        """

        averaged_solution = torch.zeros_like(self.latest_model)
        # averaged_solution = np.zeros(self.latest_model.shape)
        if self.simple_average:
            num = 0
            for num_sample, local_solution in colns:
                num += 1
                averaged_solution += local_solution
            averaged_solution /= num
        else:
            for num_sample, local_solution in colns:
                averaged_solution += num_sample * local_solution
            averaged_solution /= self.all_train_data_num

        # averaged_solution = from_numpy(averaged_solution, self.gpu)
        return averaged_solution.detach()

    def test_latest_model_on_traindata(self, round_i):
        # Collect self.stats from total train data
        begin_time = time.time()
        self.stats_from_train_data = self.local_test(use_eval_data=False)

        # Record the global gradient
        model_len = len(self.latest_model)
        global_grads = np.zeros(model_len)
        num_samples = []
        local_grads = []

        for c in self.clients:
            (num, client_grad), stat = c.solve_grad()
            local_grads.append(client_grad)
            num_samples.append(num)
            global_grads += client_grad * num
        global_grads /= np.sum(np.asarray(num_samples))
        self.stats_from_train_data['gradnorm'] = np.linalg.norm(global_grads)

        # Measure the gradient difference
        difference = 0.
        for idx in range(len(self.clients)):
            difference += np.sum(np.square(global_grads - local_grads[idx]))
        difference /= len(self.clients)
        self.stats_from_train_data['graddiff'] = difference
        end_time = time.time()

        # self.metrics.update_train_self.stats(round_i, self.stats_from_train_data)
        # if self.print_result:
        print('\n>>> Round: {: >4d} / Acc: {:.3%} / Loss: {:.4f} /'
                ' Grad Norm: {:.4f} / Grad Diff: {:.4f} / Time: {:.2f}s'.format(
                round_i, self.stats_from_train_data['acc'], self.stats_from_train_data['loss'],
                self.stats_from_train_data['gradnorm'], difference, end_time-begin_time))
        print('=' * 102 + "\n")

        self.log_round_loss = self.stats_from_train_data['loss']
        return global_grads

    def test_latest_model_on_evaldata(self, round_i):
        # Collect self.stats from total eval data
        begin_time = time.time()
        self.stats_from_eval_data = self.local_test(use_eval_data=True)
        end_time = time.time()

        # if self.print_result and round_i % self.eval_every == 0:
        print('= Test = round: {} / acc: {:.3%} / '
                'loss: {:.4f} / Time: {:.2f}s'.format(
                round_i, self.stats_from_eval_data['acc'],
                self.stats_from_eval_data['loss'], end_time-begin_time))
        print('=' * 102 + "\n")

        self.acc = self.stats_from_eval_data['acc']

        # self.metrics.update_eval_self.stats(round_i, self.stats_from_eval_data)

    def local_test(self, use_eval_data=True):
        assert self.latest_model is not None
        # self.worker.set_flat_model_params(self.latest_model)

        num_samples = []
        tot_corrects = []
        losses = []
        for c in self.clients:
            c.set_flat_model_params(self.latest_model)
            tot_correct, num_sample, loss = c.local_test(use_eval_data=use_eval_data)

            tot_corrects.append(tot_correct)
            num_samples.append(num_sample)
            losses.append(loss)

        ids = [c.cid for c in self.clients]
        groups = [c.group for c in self.clients]

        self.stats = {'acc': sum(tot_corrects) / sum(num_samples),
                 'loss': sum(losses) / sum(num_samples),
                 'num_samples': num_samples, 'ids': ids, 'groups': groups}

        return self.stats
