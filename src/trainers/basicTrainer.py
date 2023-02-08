###########################################
##  Proposed Sampling Scheme
###########################################

from src.trainers.base_multi import BaseTrainer
# from src.trainers.base_bk import BaseTrainer
from src.models.model import choose_model
from src.models.worker import LrdWorker
# from src.optimizers.gd import GD
import numpy as np
import torch


criterion = torch.nn.CrossEntropyLoss()


class FedAvgTrainer(BaseTrainer):
    def __init__(self, options, trainerConfig):
        model = choose_model(options)
        # self.move_model_to_gpu(model, options)
        # self.num_epoch = options['num_epoch']
        # worker = LrdWorker(model, self.optimizer, options)
        super(FedAvgTrainer, self).__init__(options, trainerConfig)


    def train(self):
        print('>>> Select {} clients per round \n'.format(self.clients_per_round))

        # Fetch latest flat model parameter
        self.latest_model = self.worker.get_flat_model_params().detach()

        total_time = list()

        for round_i in range(self.num_round):

            # Test latest model on train data
            # Test on Server
            self.test_latest_model_on_traindata(round_i)
            self.test_latest_model_on_evaldata(round_i)

            # Add update log 
            self.logExperimentInfo['acc'].append(self.acc)
            self.logExperimentInfo['global_loss'].append(self.log_round_loss)
            self.logExperimentInfo['round_time'].append(self.log_round_time)

            # Select all clients
            selected_clients = self.select_clients(seed=round_i)
            
            # Solve minimization locally
            solns, stats = self.local_train(round_i, selected_clients)

            self.log_round_time = self.get_real_time(stats)

            total_time.append(self.log_round_time)

            # Update latest model
            self.latest_model = self.aggregate(solns)

            self.worker.optimizer.step()

            self.logExperimentInfo['sel_clients'].append([c.cid for c in selected_clients])
   
        # Test final model on train data
        # self.test_latest_model_on_traindata(self.num_round)
        print(sum(total_time))
        print(np.average(total_time))
        self.save_log()
        self.end_train()
        # self.test_latest_model_on_evaldata(self.num_round)

    def aggregate(self, solns, **kwargs):
        averaged_solution = torch.zeros_like(self.latest_model)
        # averaged_solution = np.zeros(self.latest_model.shape)

        num = 0
        for num_sample, local_solution in solns:
            num += 1
            averaged_solution += local_solution
        averaged_solution /= num

        return averaged_solution.detach()
