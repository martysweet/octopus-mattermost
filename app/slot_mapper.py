# There are 48 slots in a day (30 minute intervals)
# 0 = 00:00 - 00:30
# ..
# 47 = 23:00 - 23:30
# We map ordered data into these slots, so we don't have to worry about time comparison/iso matching at runtime.
class SlotMapper:

    slots = []
    expected_size = 48

    def __init__(self, default=-1):
        self.slots = [default] * self.expected_size

    def map(self, dataset, ts_key, value_key):
        if len(dataset) != self.expected_size:
            raise ValueError(f"Dataset length is {len(dataset)}, expected {self.expected_size} items")

        return self.__mapper__(dataset, ts_key, value_key)

    def map_from_sparse(self, sparse_dataset, ts_key, value_key):
        self.__mapper__(sparse_dataset, ts_key, value_key)

    def __mapper__(self, sparse_dataset, ts_key, value_key):
        # Order the data by timestamp, with the oldest first
        ordered_dataset = sorted(sparse_dataset, key=lambda k: k[ts_key])

        # Use this value as the default
        self.slots[0] = ordered_dataset[0][value_key]

        # Read the rest of the dataset into the slots
        for i in range(1, len(ordered_dataset)):
            # Take the data['ts_key'] and convert it to a slot number
            # A slot number is 30 minutes, so 00:00 => 0, 00:30 => 1, 01:00 => 2, etc
            # We can do this by taking the first 2 digits (hours) and multiplying by 2
            # Then we add 1 if the last 2 digits are 30 or more

            ts = ordered_dataset[i][ts_key]
            slot = int(ts[11:13]) * 2
            if int(ts[14:16]) >= 30:
                slot += 1

            self.slots[slot] = ordered_dataset[i][value_key]

        # Fill in any gaps with the value before it
        for i in range(1, len(self.slots)):
            if self.slots[i] == -1:
                self.slots[i] = self.slots[i - 1]

    def get(self):
        return self.slots

    @staticmethod
    def product_maps(a, b):
        return [a * b for a, b in zip(a, b)]