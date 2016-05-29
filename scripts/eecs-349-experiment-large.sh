python train.py \
       --data_file=data/my.txt \
       --dropout=0.5 \
       --num_epochs=5 \
       --hidden_size=8 \
       --num_layers=1 \
       --model="rnn" \
       --batch_size=64 \
       --output_dir=large \

tensorboard --logdir=large/tensorboard_log/ --port=6007
