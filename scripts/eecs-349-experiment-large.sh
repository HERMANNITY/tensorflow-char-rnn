python train.py \
       --data_file=data/my.txt \
       --dropout=0.3 \
       --num_epochs=50 \
       --hidden_size=128 \
       --num_layers=2 \
       --model="rnn" \
       --batch_size=100 \
       --output_dir=large \

tensorboard --logdir=large/tensorboard_log/ --port=6007
