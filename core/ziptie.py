""" 
the Ziptie class 
"""
import copy
import numpy as np
import tools

class ZipTie(object):
    """ 
    An incremental unsupervised clustering algorithm

    Input channels are clustered together into mutually co-active sets.
    A helpful metaphor is bundling cables together with zip ties.
    Cables that carry related signals are commonly co-active, 
    and are grouped together. Cables that are co-active with existing
    bundles can be added to those bundles. A single cable may be ziptied
    into several different bundles. Co-activity is estimated 
    incrementally, that is, the algorithm updates the estimate after 
    each new set of signals is received. 

    Zipties are arranged hierarchically within the agent's drivetrain. 
    The agent begins with only one ziptie and creates subsequent
    zipties as previous ones mature. 
    """
    #def __init__(self, max_num_cables, max_num_bundles, 
    #             max_cables_per_bundle=None,
    #             name='ziptie_', in_gearbox=False):
    def __init__(self, min_cables, exploit=False,
                 name='anonymous', level=0):
        """ 
        Initialize each map, pre-allocating max_num_bundles 
        """
        self.exploit = exploit
        self.name = name
        self.level = level
        self.max_num_cables = int(2 ** np.ceil(np.log2(min_cables)))
        self.max_num_bundles = self.max_num_cables
        '''
        # Identify whether the ziptie is located in a gearbox or in a cog.
        # This changes several aspects of its operation. 
        self.in_gearbox = in_gearbox
        self.max_num_cables = max_num_cables
        self.max_num_bundles = max_num_bundles
        if max_cables_per_bundle is None:
            self.max_cables_per_bundle = int(self.max_num_cables / 
                                             self.max_num_bundles)
        else:
            self.max_cables_per_bundle = max_cables_per_bundle
        '''
        self.num_bundles = 0
        # User-defined constants
        self.NUCLEATION_THRESHOLD = .1
        self.NUCLEATION_ENERGY_RATE = 1e-3 * 2**-level
        self.AGGLOMERATION_THRESHOLD = .1
        self.AGGLOMERATION_ENERGY_RATE = 1e-2 * 2**-level
        '''
        if self.in_gearbox:
            # These seem to strike a nice balance between 
            # feature quality and learning speed
            self.AGGLOMERATION_ENERGY_RATE = 1.e-3
        else:
            # For zipties within cogs
            self.AGGLOMERATION_ENERGY_RATE = 1.e-4
        '''
        '''
        # Exponent for calculating the generalized mean of signals in 
        # order to find bundle activities (float, x != 0)
        self.MEAN_EXPONENT = -2
        # Exponent controlling the strength of inhibition between bundles
        self.ACTIVATION_WEIGHTING_EXPONENT = 512
        '''
        # The rate at which cable activities decay (float, 0 < x < 1)
        self.ACTIVITY_DECAY_RATE = 2 ** (-self.level)

        self.bundles_full = False        
        self.bundle_activities = np.zeros((self.max_num_bundles, 1))
        self.cable_activities = np.zeros((self.max_num_cables, 1))
        map_size = (self.max_num_bundles, self.max_num_cables)
        #self.bundle_map = np.zeros(map_size)
        self.bundle_map = np.ones(map_size) * np.nan
        self.agglomeration_energy = np.zeros(map_size)
        self.nucleation_energy = np.zeros((self.max_num_cables, 
                                           self.max_num_cables))

    def step_up(self, new_cable_activities):
        """ 
        Update co-activity estimates and calculate bundle activity 
        """
        if new_cable_activities.size < self.max_num_cables:
            new_cable_activities = tools.pad(new_cable_activities, 
                                             (self.max_num_cables, 1))
        # debug: don't adapt cable activities 
        self.cable_activities = new_cable_activities
        self.cable_activities = tools.bounded_sum2(new_cable_activities, 
                self.cable_activities * (1. - self.ACTIVITY_DECAY_RATE))
        '''
        """
        Find bundle activities by taking the generalized mean of
        the signals with a negative exponent.
        The negative exponent weights the lower signals more heavily.
        Make a first pass at the bundle activation levels by 
        multiplying across the bundle map.
        """
        initial_bundle_activities = tools.generalized_mean(
                self.cable_activities, self.bundle_map.T, self.MEAN_EXPONENT)

        bundle_contribution_map = np.zeros(self.bundle_map.shape)
        bundle_contribution_map[np.nonzero(self.bundle_map)] = 1.
        # Use aggressive lateral inhibition between bundles so that 
        # cables' activity is monopolized by the strongest-activated bundle.
        activated_bundle_map = (initial_bundle_activities * 
                                bundle_contribution_map)
        # Add just a little noise to break ties
        activated_bundle_map += 1e-4 * np.random.random_sample(
                activated_bundle_map.shape)
        # Find the largest bundle activity that each input contributes to
        max_activation = (np.max(activated_bundle_map, axis=0) + 
                          tools.EPSILON)
        # Divide the energy that each input contributes to each bundle
        input_inhibition_map = np.power(activated_bundle_map / max_activation, 
                                        self.ACTIVATION_WEIGHTING_EXPONENT)
        # Find the effective strength of each cable to each bundle 
        # after inhibition.
        inhibited_cable_activities = (input_inhibition_map * 
                                      self.cable_activities.T)
        final_bundle_activities = tools.generalized_mean(
                inhibited_cable_activities.T, self.bundle_map.T, 
                self.MEAN_EXPONENT)
        self.bundle_activities = final_bundle_activities
        '''
        """
        Find bundle activities by taking the minimum input value
        in the set of cables in the bundle.
        """
        #self.bundle_map[np.where(self.bundle_map==0.)] = np.nan
        bundle_components = self.bundle_map * self.cable_activities.T 
        # TODO: consider other ways to calculate bundle energies
        self.bundle_energies = np.nansum(bundle_components,
                                         axis=1)[:,np.newaxis]
        self.bundle_energies[np.where(np.isnan(self.bundle_energies))] = 0.
        #print 'be', self.bundle_energies.T
        energy_index = np.argsort(self.bundle_energies.ravel())[:,np.newaxis]
        #print 'ei', energy_index.T
        max_energy = self.bundle_energies[energy_index[-1]]
        #print 'max_e', max_energy
        mod_energies = self.bundle_energies - (
                max_energy * ( (self.num_bundles - energy_index) / 
                               (self.num_bundles + tools.EPSILON) ))
        #print 'me', mod_energies.T
        
        self.bundle_activities = np.nanmin(bundle_components,
                                           axis=1)[:,np.newaxis]
        #print 'ba before', self.bundle_activities.T
        self.bundle_activities[np.where(mod_energies < 0.)] = 0.
        self.bundle_activities = np.nan_to_num(self.bundle_activities)
        #self.bundle_activities[np.where(np.isnan(self.bundle_activities))] = 0.
        #print 'ba', self.bundle_activities.T

        self.reconstruction = np.nanmax(self.bundle_activities * 
                                        self.bundle_map, 
                                        axis=0)[:, np.newaxis]
        self.reconstruction[np.isnan(self.reconstruction)] = 0.
        self.nonbundle_activities = self.cable_activities - self.reconstruction
        #print 'recon', self.reconstruction.T
        #print 'nba', self.nonbundle_activities.T
        '''
        # Calculate how much energy each input has left to contribute 
        # to the co-activity estimate. 
        final_activated_bundle_map = (final_bundle_activities * 
                                      bundle_contribution_map)
        combined_weights = np.sum(final_activated_bundle_map, 
                                  axis=0)[:,np.newaxis]
        '''
        '''
        if self.in_gearbox:
            self.nonbundle_activities = (cable_activities * 
                    2 ** -np.sum(self.bundle_map, axis=0)[:,np.newaxis])
        else:
            self.nonbundle_activities = np.maximum(0., cable_activities - 
                                                   combined_weights)
        self.nonbundle_activities = np.maximum(0., self.cable_activities - 
                                               combined_weights)
        #self.cable_activities = cable_activities
        '''
        # As appropriate update the co-activity estimate and 
        # create new bundles
        if not self.exploit:
            if not self.bundles_full:
                self._create_new_bundles()
            self._grow_bundles()
        return self.bundle_activities

    def _create_new_bundles(self):
        """ 
        If the right conditions have been reached, create a new bundle 
        """
        # Bundle space is a scarce resource. Decay the energy.        
        self.nucleation_energy -= (self.cable_activities *
                                   self.cable_activities.T *
                                   self.nucleation_energy * 
                                   self.NUCLEATION_ENERGY_RATE)
        self.nucleation_energy += (self.nonbundle_activities * 
                                   self.nonbundle_activities.T * 
                                   #(1. - self.nucleation_energy) *
                                   self.NUCLEATION_ENERGY_RATE) 
        # Don't accumulate nucleation energy between a cable and itself
        ind = np.arange(self.cable_activities.size).astype(int)
        self.nucleation_energy[ind,ind] = 0.

        cable_indices = np.where(self.nucleation_energy > 
                                 self.NUCLEATION_THRESHOLD)
        #print 'ne'
        #print self.nucleation_energy
        # Add a new bundle if appropriate
        if cable_indices[0].size > 0:
            # Identify the newly created bundle's cables.
            # Randomly pick a new cable from the candidates, 
            # if there is more than one
            pair_index = np.random.randint(cable_indices[0].size)
            cable_index_a = cable_indices[0][pair_index]
            cable_index_b = cable_indices[1][pair_index]
            #cable_index = cable_indices[0][int(np.random.random_sample() * 
            #                               cable_indices[0].size)]
            # Create the new bundle in the bundle map.
            #self.bundle_map[self.num_bundles, cable_index] = 1.
            self.bundle_map[self.num_bundles, cable_index_a] = 1.
            self.bundle_map[self.num_bundles, cable_index_b] = 1.
            self.num_bundles += 1
            if self.num_bundles == self.max_num_bundles:
                self.bundles_full = True
            # Reset the accumulated nucleation and agglomeration energy
            # for the two cables involved.
            #self.nucleation_energy[cable_index, 0] = 0.
            #self.agglomeration_energy[:, cable_index] = 0.
            self.nucleation_energy[cable_index_a, :] = 0.
            self.nucleation_energy[cable_index_b, :] = 0.
            self.nucleation_energy[:, cable_index_a] = 0.
            self.nucleation_energy[:, cable_index_b] = 0.
            self.agglomeration_energy[:, cable_index_a] = 0.
            self.agglomeration_energy[:, cable_index_b] = 0.
        return 
          
    def _grow_bundles(self):
        """ 
        Update an estimate of co-activity between all cables 
        """
        #coactivities = np.dot(self.bundle_activities, 
        #                      self.nonbundle_activities.T)
        coactivities = self.bundle_activities * self.nonbundle_activities.T
        #print self.name
        #print 'ca', np.nonzero(coactivities)
        #print 'ba', self.bundle_activities.T
        #print 'nba', self.nonbundle_activities.T

        # Each cable's nonbundle activity is distributed to 
        # agglomeration energy with each bundle proportionally 
        # to their coactivities.
        # Decay the energy        
        self.agglomeration_energy -= (self.cable_activities.T *
                                      self.agglomeration_energy * 
                                      self.AGGLOMERATION_ENERGY_RATE)
        self.agglomeration_energy += (coactivities * 
                                      #(1. - self.agglomeration_energy) *
                                      self.AGGLOMERATION_ENERGY_RATE)
        #print self.name
        #print 'ae', np.sort(self.agglomeration_energy[np.nonzero(np.nan_to_num(
        #        self.agglomeration_energy))].ravel())
        '''
        # For any bundles that are already full, don't change their coactivity
        # TODO: make this more elegant than enforcing a hard maximum count
        full_bundles = np.zeros((self.max_num_bundles, 1))
        cables_per_bundle = np.sum(self.bundle_map, axis=1)[:,np.newaxis]
        full_bundles[np.where(cables_per_bundle >= 
                              self.max_cables_per_bundle)] = 1.
        self.agglomeration_energy *= 1 - full_bundles
        '''

        # Don't accumulate agglomeration energy between cables already 
        # in the same bundle 
        self.agglomeration_energy *= 1 - np.nan_to_num(self.bundle_map)

        new_candidates = np.where(self.agglomeration_energy >= 
                                  self.AGGLOMERATION_THRESHOLD)
        num_candidates =  new_candidates[0].size 
        if num_candidates > 0:
            candidate_index = np.random.randint(num_candidates) 
            candidate_cable = new_candidates[1][candidate_index]
            candidate_bundle = new_candidates[0][candidate_index]
            self.bundle_map[candidate_bundle, candidate_cable] = 1.
            #self.nucleation_energy[candidate_cable, 0] = 0.
            self.nucleation_energy[candidate_cable, :] = 0.
            self.nucleation_energy[:, candidate_cable] = 0.
            self.agglomeration_energy[:, candidate_cable] = 0.
            #print 'bundle grown!', candidate_bundle, candidate_cable
        return
        
        '''
    def step_down(self, bundle_goals):
        """ 
        Project the bundle goal values to the appropriate cables

        Multiply the bundle goals across the cables that contribute 
        to them, and perform a bounded sum over all bundles to get 
        the estimated activity associated with each cable.
        """
        if bundle_goals.size > 0:
            bundle_goals = tools.pad(bundle_goals, (self.max_num_bundles, 0))
            cable_activity_goals = tools.bounded_sum(self.bundle_map * 
                                                     bundle_goals, axis=0)
        else:
            cable_activity_goals = np.zeros((self.max_num_cables, 1))
        return cable_activity_goals
        '''
        
    def get_index_projection(self, bundle_index):
        """ 
        Project bundle indices down to their cable indices 
        """
        projection = copy.deepcopy(self.bundle_map[bundle_index,:])
        projection[np.isnan(projection)] = 0.
        return projection
        
    def bundles_created(self):
        return self.num_bundles

        '''
    def cable_fraction_in_bundle(self, bundle_index):
        """
        What fraction of the cables have been included in bundles?
        """
        cable_count = np.nonzero(self.bundle_map[bundle_index,:])[0].size
        cable_fraction = float(cable_count) / float(self.max_cables_per_bundle)
        return cable_fraction
        '''

    def visualize(self, save_eps=False):
        print self.name, '0', np.nonzero(np.nan_to_num(np.copy(
                self.bundle_map)))[0]
        print self.name, '1', np.nonzero(np.nan_to_num(np.copy(
                self.bundle_map)))[1]
        print self.max_num_bundles, 'bundles maximum'
        tools.visualize_array(self.bundle_map, label=self.name + '_bundle_map')
        tools.visualize_array(self.agglomeration_energy, 
                              label=self.name + '_agg_energy')
        pass
